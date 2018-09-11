import logging
import random
import re
import uuid

from streamlink.compat import unquote
from streamlink.exceptions import NoStreamsError, PluginError
from streamlink.plugin import Plugin, PluginArgument, PluginArguments
from streamlink.plugin.api import useragents, validate
from streamlink.stream import DASHStream, HLSStream
from streamlink.utils import parse_json

from websocket import create_connection

log = logging.getLogger(__name__)


class MyFreeCams(Plugin):
    '''Streamlink Plugin for MyFreeCams

    UserName
        - https://m.myfreecams.com/models/UserName
        - https://myfreecams.com/#UserName
        - https://profiles.myfreecams.com/UserName
        - https://www.myfreecams.com/#UserName
        - https://www.myfreecams.com/UserName
    User ID with php fallback
        - https://myfreecams.com/?id=10101010
    '''

    JS_SERVER_URL = 'https://www.myfreecams.com/_js/serverconfig.js'
    PHP_URL = 'https://www.myfreecams.com/php/FcwExtResp.php?respkey={respkey}&type={type}&opts={opts}&serv={serv}'

    _url_re = re.compile(r'''https?://(?:\w+\.)?myfreecams\.com/
        (?:
            (?:models/)?\#?(?P<username>\w+)
            |
            \?id=(?P<user_id>\d+)
        )''', re.VERBOSE)
    _dict_re = re.compile(r'''(?P<data>{.*})''')
    _socket_re = re.compile(r'''(\w+) (\w+) (\w+) (\w+) (\w+)''')

    _data_schema = validate.Schema(
        {
            'nm': validate.text,
            'sid': int,
            'uid': int,
            'vs': int,
            validate.optional('u'): {
                'camserv': int
            }
        }
    )

    arguments = PluginArguments(
        PluginArgument(
            'dash',
            action='store_true',
            default=False,
            help='''
            Use DASH streams as an alternative source.

                %(prog)s --myfreecams-dash <url> [stream]

            '''
        )
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _php_fallback(self, username, user_id, php_message):
        '''Use the php website as a fallback when
            - UserId was used
            - Username failed for WebSocket
            - VS = 90 and no camserver

        Args:
            username: Model Username
            user_id: Model UserID
            php_message: data from self._websocket_data
        Returns:
            message: data to create a video url.
        '''
        log.debug('Attempting to use php fallback')
        php_data = self._dict_re.search(php_message)
        if php_data is None:
            raise NoStreamsError(self.url)

        php_data = parse_json(php_data.group('data'))
        php_url = self.PHP_URL.format(
            opts=php_data['opts'],
            respkey=php_data['respkey'],
            serv=php_data['serv'],
            type=php_data['type']
        )
        php_params = {
            'cid': 3149,
            'gw': 1
        }
        res = self.session.http.get(php_url, params=php_params)

        if username:
            _username_php_re = str(username)
            _uid_php_re = r'''\d+'''
        elif user_id:
            _username_php_re = r'''[^"']+'''
            _uid_php_re = str(user_id)
        else:
            raise NoStreamsError(self.url)

        _data_php_re = re.compile(
            r'''\[["'](?P<username>{0})["'],(?P<sid>\d+),'''.format(_username_php_re)
            + r'''(?P<uid>{0}),(?P<vs>\d+),[^,]+,[^,]+,(?P<camserv>\d+)[^\]]+\]'''.format(_uid_php_re))

        match = _data_php_re.search(res.text)
        if match is None:
            raise NoStreamsError(self.url)

        data = {
            'nm': str(match.group('username')),
            'sid': int(match.group('sid')),
            'uid': int(match.group('uid')),
            'vs': int(match.group('vs')),
            'u': {
                'camserv': int(match.group('camserv'))
            }
        }
        return data

    def _websocket_data(self, username, chat_servers):
        '''Get data from the websocket.

        Args:
            username: Model Username
            chat_servers: servername from self._get_servers

        Returns:
            message: data to create a video url.
            php_message: data for self._php_fallback
        '''
        try_to_connect = 0
        while (try_to_connect < 5):
            try:
                xchat = str(random.choice(chat_servers))
                host = 'wss://{0}.myfreecams.com/fcsl'.format(xchat)
                ws = create_connection(host)
                ws.send('hello fcserver\n\0')
                r_id = str(uuid.uuid4().hex[0:32])
                ws.send('1 0 0 20071025 0 {0}@guest:guest\n'.format(r_id))
                log.debug('Websocket server {0} connected'.format(xchat))
                try_to_connect = 5
            except Exception:
                try_to_connect += 1
                log.debug('Failed to connect to WS server: {0} - try {1}'.format(xchat, try_to_connect))
                if try_to_connect == 5:
                    log.error('can\'t connect to the websocket')
                    raise

        buff = ''
        php_message = ''
        ws_close = 0
        while ws_close == 0:
            socket_buffer = ws.recv()
            socket_buffer = buff + socket_buffer
            buff = ''
            while True:
                ws_answer = self._socket_re.search(socket_buffer)
                if bool(ws_answer) == 0:
                    break

                FC = ws_answer.group(1)
                FCTYPE = int(FC[4:])

                message_length = int(FC[0:4])
                message = socket_buffer[4:4 + message_length]

                if len(message) < message_length:
                    buff = ''.join(socket_buffer)
                    break

                message = unquote(message)

                if FCTYPE == 1 and username:
                    ws.send('10 0 0 20 0 {0}\n'.format(username))
                elif FCTYPE == 81:
                    php_message = message
                    if username is None:
                        ws_close = 1
                elif FCTYPE == 10:
                    ws_close = 1

                socket_buffer = socket_buffer[4 + message_length:]

                if len(socket_buffer) == 0:
                    break

        ws.send('99 0 0 0 0')
        ws.close()
        return message, php_message

    def _get_servers(self):
        res = self.session.http.get(self.JS_SERVER_URL)
        servers = parse_json(res.text)
        return servers

    def _get_camserver(self, servers, key):
        server_type = None
        value = None

        h5video_servers = servers['h5video_servers']
        ngvideo_servers = servers['ngvideo_servers']
        wzobs_servers = servers['wzobs_servers']

        if h5video_servers.get(str(key)):
            value = h5video_servers[str(key)]
            server_type = 'h5video_servers'
        elif wzobs_servers.get(str(key)):
            value = wzobs_servers[str(key)]
            server_type = 'wzobs_servers'
        elif ngvideo_servers.get(str(key)):
            value = ngvideo_servers[str(key)]
            server_type = 'ngvideo_servers'

        return value, server_type

    def _get_streams(self):
        self.session.http.headers.update({'User-Agent': useragents.FIREFOX})
        log.debug('Version 2018-07-12')
        log.info('This is a custom plugin. ')
        match = self._url_re.match(self.url)
        username = match.group('username')
        user_id = match.group('user_id')

        servers = self._get_servers()
        chat_servers = servers['chat_servers']

        message, php_message = self._websocket_data(username, chat_servers)

        if user_id and not username:
            data = self._php_fallback(username, user_id, php_message)
        else:
            log.debug('Attempting to use WebSocket data')
            data = self._dict_re.search(message)
            if data is None:
                raise NoStreamsError(self.url)
            data = parse_json(data.group('data'), schema=self._data_schema)

        vs = data['vs']
        ok_vs = [0, 90]
        if vs not in ok_vs:
            if vs == 2:
                log.info('Model is currently away')
            elif vs == 12:
                log.info('Model is currently in a private show')
            elif vs == 13:
                log.info('Model is currently in a group show')
            elif vs == 127:
                log.info('Model is currently offline')
            else:
                log.error('Stream status: {0}'.format(vs))
            raise NoStreamsError(self.url)

        log.debug('VS: {0}'.format(vs))

        nm = data['nm']
        uid = data['uid']
        uid_video = uid + 100000000
        camserver = data['u']['camserv']

        server, server_type = self._get_camserver(servers, camserver)

        if server is None and not user_id:
            fallback_data = self._php_fallback(username, user_id, php_message)
            camserver = fallback_data['u']['camserv']
            server, server_type = self._get_camserver(servers, camserver)

        log.info('Username: {0}'.format(nm))
        log.info('User ID:  {0}'.format(uid))

        if not server:
            raise PluginError('Missing video server')

        log.debug('Video server: {0}'.format(server))
        log.debug('Video server_type: {0}'.format(server_type))

        if server_type == 'h5video_servers':
            DASH_VIDEO_URL = 'https://{0}.myfreecams.com/NxServer/ngrp:mfc_{1}.f4v_desktop/manifest.mpd'.format(server, uid_video)
            HLS_VIDEO_URL = 'https://{0}.myfreecams.com/NxServer/ngrp:mfc_{1}.f4v_mobile/playlist.m3u8'.format(server, uid_video)
        elif server_type == 'wzobs_servers':
            DASH_VIDEO_URL = ''
            HLS_VIDEO_URL = 'https://{0}.myfreecams.com/NxServer/ngrp:mfc_a_{1}.f4v_mobile/playlist.m3u8'.format(server, uid_video)
        elif server_type == 'ngvideo_servers':
            raise PluginError('ngvideo_servers are not supported.')
        else:
            raise PluginError('Unknow server type.')

        log.debug('HLS URL: {0}'.format(HLS_VIDEO_URL))
        for s in HLSStream.parse_variant_playlist(self.session,
                                                  HLS_VIDEO_URL).items():
            yield s

        if DASH_VIDEO_URL and self.get_option('dash'):
            log.debug('DASH URL: {0}'.format(DASH_VIDEO_URL))
            for s in DASHStream.parse_manifest(self.session,
                                               DASH_VIDEO_URL).items():
                yield s


__plugin__ = MyFreeCams

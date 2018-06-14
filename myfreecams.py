import json
import logging
import random
import re
import uuid

from streamlink.compat import unquote
from streamlink.exceptions import NoStreamsError
from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.stream import HLSStream

from websocket import create_connection

log = logging.getLogger(__name__)


class MyFreeCams(Plugin):
    '''streamlink Plugin for MyFreeCams

    UserName
        - https://m.myfreecams.com/models/UserName
        - https://myfreecams.com/#UserName
        - https://profiles.myfreecams.com/UserName
        - https://www.myfreecams.com/#UserName
        - https://www.myfreecams.com/UserName
    User ID with php fallback
        - https://myfreecams.com/?id=10101010
    '''

    HLS_VIDEO_URL = 'http://{0}.myfreecams.com:1935/NxServer/ngrp:mfc_{1}.f4v_mobile/playlist.m3u8'
    JS_SERVER_URL = 'https://www.myfreecams.com/_js/serverconfig.js'
    PHP_URL = 'https://www.myfreecams.com/php/FcwExtResp.php?respkey={respkey}&type={type}&opts={opts}&serv={serv}'

    _url_re = re.compile(r'''https?://(?:\w+\.)?myfreecams\.com/(?:(?:models/)?#?(?P<username>\w+)|\?id=(?P<user_id>\d+))''')
    _dict_re = re.compile(r'''(?P<data>{.*})''')
    _socket_re = re.compile(r'''(\w+) (\w+) (\w+) (\w+) (\w+)''')

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

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
        log.debug('Trying to use php fallback')
        php_data = self._dict_re.search(php_message)
        if php_data is None:
            raise NoStreamsError(self.url)

        php_data = json.loads(php_data.group('data'))
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
        res = http.get(php_url, params=php_params)

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
        while (try_to_connect < 3):
            try:
                xchat = str(random.choice(chat_servers))
                host = 'wss://{0}.myfreecams.com/fcsl'.format(xchat)
                ws = create_connection(host)
                ws.send('hello fcserver\n\0')
                r_id = str(uuid.uuid4().hex[0:32])
                ws.send('1 0 0 20071025 0 {0}@guest:guest\n'.format(r_id))
                log.debug('Websocket server {0} connected'.format(xchat))
                try_to_connect = 3
            except Exception:
                try_to_connect = try_to_connect + 1
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
        '''Gets all servers.'''
        res = http.get(self.JS_SERVER_URL)
        servers = json.loads(res.text)

        chat_servers = servers.get('chat_servers')
        h5video_servers = servers.get('h5video_servers')

        return chat_servers, h5video_servers

    def _get_streams(self):
        http.headers.update({'User-Agent': useragents.FIREFOX})
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        match = self._url_re.match(self.url)
        username = match.group('username')
        user_id = match.group('user_id')

        chat_servers, video_servers = self._get_servers()

        message, php_message = self._websocket_data(username, chat_servers)

        if user_id and not username:
            data = self._php_fallback(username, user_id, php_message)
        else:
            log.debug('Trying to use WebSocket data')
            data = self._dict_re.search(message)
            if data is None:
                raise NoStreamsError(self.url)
            data = json.loads(data.group('data'))

        vs = data.get('vs')
        ok_vs = [0, 90]
        if vs not in ok_vs:
            if vs is 2:
                log.info('Model is currently away')
            elif vs is 12:
                log.info('Model is currently in a private show')
            elif vs is 13:
                log.info('Model is currently in a group show')
            elif vs is 127:
                log.info('Model is currently offline')
            else:
                log.error('Stream status: {0}'.format(vs))
            raise NoStreamsError(self.url)

        nm = data.get('nm')
        uid = data.get('uid')
        uid_video = uid + 100000000
        camserver = data['u']['camserv']
        server = video_servers.get(str(camserver))

        if server is None and not user_id:
            fallback_data = self._php_fallback(username, user_id, php_message)
            camserver = fallback_data['u']['camserv']
            server = video_servers.get(str(camserver))

        log.info('Username: {0}'.format(nm))
        log.info('User ID:  {0}'.format(uid))
        log.debug('Video server: {0}'.format(server))
        if server:
            hls_url = self.HLS_VIDEO_URL.format(server, uid_video)
            log.debug('HLS URL: {0}'.format(hls_url))
            for s in HLSStream.parse_variant_playlist(self.session, hls_url).items():
                yield s


__plugin__ = MyFreeCams

   
        
        

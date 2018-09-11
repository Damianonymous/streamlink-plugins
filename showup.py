import logging
import random
import re
import websocket

from streamlink.plugin import Plugin
from streamlink.plugin.api import validate, utils
from streamlink.stream import RTMPStream

SWF_URL = 'http://showup.tv/flash/suStreamer.swf'
RANDOM_UID = '%032x' % random.getrandbits(128)
JSON_UID = u'{"id":0,"value":["%s",""]}'
JSON_CHANNEL = u'{"id":2,"value":["%s"]}'

_url_re = re.compile(r'https?://(\w+.)?showup\.tv/(?P<channel>[A-Za-z0-9_-]+)')
_websocket_url_re = re.compile(r'''socket\.connect\(["'](?P<ws>[^"']+)["']\)''')
_schema = validate.Schema(validate.get('value'))

log = logging.getLogger(__name__)


class ShowUp(Plugin):
    @classmethod
    def can_handle_url(cls, url):
        return _url_re.match(url)

    def _get_stream_id(self, channel, ws_url):
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        ws.send(JSON_UID % RANDOM_UID)
        ws.send(JSON_CHANNEL % channel)
        # STREAM_ID
        result = ws.recv()
        data = utils.parse_json(result, schema=_schema)
        log.debug('DATA 1 {0}'.format(data))
        if 'failure' in data:
            ws.close()
            return False, False

        # RTMP CDN
        result_2 = ws.recv()
        data2 = utils.parse_json(result_2, schema=_schema)
        log.debug('DATA 2 {0}'.format(data2))
        if 'failure' in data2:
            ws.close()
            return False, False

        # ERROR
        result_3 = ws.recv()
        data3 = utils.parse_json(result_3, schema=_schema)
        log.debug('DATA 3 {0}'.format(data3))
        if 'failure' in data3:
            ws.close()
            return False, False

        return data[0], data2[1]

    def _get_websocket(self, html):
        ws_url = _websocket_url_re.search(html)
        if ws_url:
            ws_host = ws_url.group('ws')
            if ':' in ws_host:
                ws_host, ws_port = ws_host.split(':')
            return 'wss://%s' % ws_host

    def _get_streams(self):
        log.debug('Version 2018-08-19')
        log.info('This is a custom plugin.')
        url_match = _url_re.match(self.url)
        channel = url_match.group('channel')
        log.debug('Channel name: {0}'.format(channel))
        self.session.http.parse_headers('Referer: %s' % self.url)
        self.session.http.parse_cookies('accept_rules=true')
        page = self.session.http.get(self.url)
        ws_url = self._get_websocket(page.text)
        log.debug('WebSocket: {0}'.format(ws_url))
        stream_id, rtmp_cdn = self._get_stream_id(channel, ws_url)
        if not (stream_id or rtmp_cdn):
            log.error('Channel is not available.')
            return
        log.debug('Stream ID: {0}'.format(stream_id))
        log.debug('RTMP CDN: {0}'.format(rtmp_cdn))
        stream = RTMPStream(self.session, {
            'rtmp': 'rtmp://{0}:1935/webrtc'.format(rtmp_cdn),
            'pageUrl': self.url,
            'playpath': '{0}_aac'.format(stream_id),
            'swfVfy': SWF_URL,
            'live': True
        })
        return {'live': stream}


__plugin__ = ShowUp

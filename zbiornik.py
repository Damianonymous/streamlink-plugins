import logging
import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import useragents, validate
from streamlink.stream import RTMPStream
from streamlink.utils import parse_json

log = logging.getLogger(__name__)


class Zbiornik(Plugin):

    SWF_URL = 'https://zbiornik.tv/wowza.swf'

    _url_re = re.compile(
        r'^https?://(?:www\.)?zbiornik\.tv/(?P<channel>[^/]+)/?$')

    _streams_re = re.compile(r'''var\sstreams\s*=\s*(?P<data>\[.+\]);''')
    _user_re = re.compile(r'''var\suser\s*=\s*(?P<data>\{[^;]+\});''')

    _user_schema = validate.Schema({
        'wowzaIam': {
            'phash': validate.text,
        }
    }, validate.get('wowzaIam'))

    _streams_schema = validate.Schema([{
        'nick': validate.text,
        'broadcasturl': validate.text,
        'server': validate.text,
        'id': validate.text,
    }])

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _get_streams(self):
        log.debug('Version 2018-07-12')
        log.info('This is a custom plugin. ')
        channel = self._url_re.match(self.url).group('channel')
        log.info('Channel: {0}'.format(channel))
        self.session.http.headers.update({'User-Agent': useragents.FIREFOX})
        self.session.http.parse_cookies('adult=1')
        res = self.session.http.get(self.url)

        m = self._streams_re.search(res.text)
        if not m:
            log.debug('No streams data found.')
            return

        m2 = self._user_re.search(res.text)
        if not m:
            log.debug('No user data found.')
            return

        _streams = parse_json(m.group('data'), schema=self._streams_schema)
        _user = parse_json(m2.group('data'), schema=self._user_schema)

        _x = []
        for _s in _streams:
            if _s.get('nick') == channel:
                _x = _s
                break

        if not _x:
            log.error('Channel is not available.')
            return

        app = 'videochat/?{0}'.format(_user['phash'])
        rtmp = 'rtmp://{0}/videochat/'.format(_x['server'])

        params = {
            'rtmp': rtmp,
            'pageUrl': self.url,
            'app': app,
            'playpath': _x['broadcasturl'],
            'swfVfy': self.SWF_URL,
            'live': True
        }
        return {'live': RTMPStream(self.session, params=params)}


__plugin__ = Zbiornik

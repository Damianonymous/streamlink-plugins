import json
import re

import requests

from urllib.parse import urljoin, urlparse, urlunparse
from streamlink.exceptions import PluginError, NoStreamsError
from streamlink.plugin.api import validate, useragents
from streamlink.plugin import Plugin
from streamlink.stream import HLSStream
from streamlink.utils import update_scheme


CONST_HEADERS = {}
CONST_HEADERS['User-Agent'] = useragents.CHROME
CONST_HEADERS['X-Requested-With'] = 'XMLHttpRequest'

url_re = re.compile(r"(http(s)?://)?(\w{2}.)?(bongacams\d*?\.com)/([\w\d_-]+)")

schema = validate.Schema({
    "status": "success"
})


class bongacams(Plugin):
    @classmethod
    def can_handle_url(self, url):
        return url_re.match(url)

    def _get_streams(self):
        match = url_re.match(self.url)

        LISTING_PATH = 'tools/listing_v3.php'

        stream_page_scheme = 'https'
        stream_page_domain = match.group(4)
        model_name = match.group(5)

        listing_url = urlunparse((stream_page_scheme, stream_page_domain, LISTING_PATH, '', '', ''))

        # create http session and set headers
        http_session = self.session.http
        http_session.headers.update(CONST_HEADERS)
        
        params = {
            "livetab": None,
            "online_only": True,
            "offset": 0,
            "model_search[display_name][text]": model_name,
            "_online_filter": 0,
            "can_pin_models": False,
            "limit": 1
        }

        response = http_session.get(listing_url, params=params)

        self.logger.debug(response.text)

        if len(http_session.cookies) == 0:
            raise PluginError("Can't get a cookies")
        if response.status_code != 200:
            self.logger.debug("response for {0}:\n{1}".format(response.request.url, response.text))
            raise PluginError("unexpected status code for {0}: {1}".format(response.url, response.status_code))

        http_session.close()
        response = response.json()
        schema.validate(response)

        if not model_name.lower() in list([model['username'].lower() for model in response['models']]):
            raise NoStreamsError(self.url)
        if str(response['online_count']) == '0':
            raise NoStreamsError(self.url)

        esid = None
        for model in response['models']:
            if model['username'].lower() == model_name.lower():
                #if model['room'] not in ('public', 'private', 'fullprivate'):
                #    raise NoStreamsError(self.url)
                esid = model.get('esid')
                model_name = model['username']

        if not esid:
            raise PluginError("unknown error, esid={0} for {1}.\nResponse: {2}".format(esid, model_name, response['models']))

        hls_url = f'https://{esid}.bcvcdn.com/hls/stream_{model_name}/playlist.m3u8'

        if hls_url:
            self.logger.debug('HLS URL: {0}'.format(hls_url))
            try:
                for s in HLSStream.parse_variant_playlist(self.session, hls_url).items():
                    yield s
            except Exception as e:
                if '404' in str(e):
                    self.logger.debug(str(e))
                    self.logger.debug('Stream is currently offline/private/away')
                else:
                    self.logger.error(str(e))
                return


__plugin__ = bongacams



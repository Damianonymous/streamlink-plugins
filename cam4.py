import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream
from datetime import datetime

STREAM_INFO = "https://www.cam4.com/rest/v1.0/profile/{0}/streamInfo"
INFO_URL = "https://www.cam4.com/rest/v1.0/search/performer/{0}"
PROFILE_URL = "https://www.cam4.com/rest/v1.0/profile/{0}/info"

_url_re = re.compile(r"https?://(\w+\.)?cam4\.com/(?P<username>\w+)")

class Cam4(Plugin):
    @classmethod
    def can_handle_url(cls, url):
        return _url_re.match(url)

    def _get_streams(self):
        match = _url_re.match(self.url)
        username = match.group("username")

        res = self.session.http.get(INFO_URL.format(username))
        data = self.session.http.json(res)

        online = data["online"]
        self.logger.info("Stream status: {0}".format("online" if online else "offline"))
        if online:
            self.logger.info("Country: {0}".format(data["country"]))
            res = self.session.http.get(PROFILE_URL.format(username))
            data = self.session.http.json(res)
            self.logger.info("City: {0}".format(data["city"]))
            self.logger.info("Body Hair: {0}".format(data["bodyHair"]))
            self.logger.info("Main Language: {0}".format(data["mainLanguage"]))
            self.logger.info("Breast Size: {0}".format(data["breastSize"]))
            self.logger.info("Birthdate: {0}".format(data["birthdate"]))
            self.logger.info("Age: {0}".format(int((datetime.now() - datetime.strptime(data["birthdate"], "%Y-%m-%d")).days / 365)))

            res = self.session.http.get(STREAM_INFO.format(username))
            data = self.session.http.json(res)
            if data["canUseCDN"]:
                sStreamURL = data["cdnURL"]
                self.logger.debug("Playlist URL : {0}".format(sStreamURL))
                for s in HLSStream.parse_variant_playlist(self.session, sStreamURL).items():
                    self.logger.debug("HLS Stream: {0}".format(s))
                    yield s
            else:
                self.logger.info("Access: private")

__plugin__ = Cam4

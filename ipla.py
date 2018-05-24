#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
from streamlink.plugin import Plugin
from streamlink.plugin.api import http, validate
from streamlink.stream import HTTPStream
URL_EPISODE_INFO = u"http://getmedia.redefine.pl/vods/get_vod/?cpid=1&media_id={media_id}"
USER_AGENT = "ipla/344 (Windows NT 6.1)"
_ipla_protocol_re = re.compile(r"ipla://[^|]+\|(?P<media_id>\w+)")
_url_re = re.compile(r"(?:https?:\/\/)?(?:www.)?ipla\.tv/.*")
_playlist_schema = validate.Schema({
    "vod":{
        "copies" : validate.all([{
            "url":validate.url(scheme=validate.any("http")),
            "quality_p": validate.text
        }])
    }
},
validate.get("vod"),
validate.get("copies")
)

class IPLA(Plugin):
    @classmethod
    def can_handle_url(cls, url):
        return _url_re.match(url)
        
    def _get_all_streams(self,data, media_id):
        for video in data:
            video_url = video["url"]
            quality = video["quality_p"]
            stream =  HTTPStream(self.session, video_url)
            yield quality, stream
                        
    def _get_streams(self):
        page = http.get(self.url)
        media_id_match = _ipla_protocol_re.search(page.text)
        if media_id_match:
            media_id = media_id_match.group("media_id")
            res = http.get(URL_EPISODE_INFO.format(media_id=media_id), headers = {'user-agent': USER_AGENT})
            try:
                data = http.json(res, schema=_playlist_schema)
            except Exception:
                return None
            return self._get_all_streams(data,media_id)

__plugin__ = IPLA


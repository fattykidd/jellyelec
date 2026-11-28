"""The focused title's resolution, HDR format and audio, as badges or as a line of text.

Jellyfin only describes a title's files (video and audio tracks) when asked about that one
title, so the screens ask once focus has rested on a poster for a moment. Scrolling past
posters then doesn't send a request for each one, and each title is asked about only once.

How it's shown is a setting (Settings > Media details): badges, the default, such as
[4K] [DOLBY VISION] [DOLBY TRUEHD ATMOS] [7.1], or one line of text.
"""

import threading
from collections import namedtuple

import xbmc
import xbmcaddon

from resources.lib import versions
from resources.lib.api import JellyfinError
from resources.lib.formatting import media_badges, media_summary
from resources.lib.kodi import log

# How long focus must rest on a title before its details are asked for.
DELAY_SECONDS = 0.4

# Add-on setting: how the details are shown.
STYLE_SETTING = "media_details_style"
BADGES = "Badges"
TEXT = "Text"
STYLES = (BADGES, TEXT)

# Most badges a screen shows (resolution, HDR format, audio codec, channels).
MAX_BADGES = 4

MediaInfo = namedtuple("MediaInfo", "text badges")
NO_INFO = MediaInfo("", [])


def style():
    return xbmcaddon.Addon().getSetting(STYLE_SETTING) or BADGES


def show(window, prefix, info):
    """Put info on a window: {prefix}_media for text, {prefix}_badge_1 to _4 for badges.
    The style not chosen is left empty, so the screen shows only the other."""
    info = info or NO_INFO
    use_badges = style() == BADGES
    window.setProperty(f"{prefix}_media", "" if use_badges else info.text)
    badges = info.badges if use_badges else []
    for number in range(1, MAX_BADGES + 1):
        window.setProperty(f"{prefix}_badge_{number}", badges[number - 1] if number <= len(badges) else "")


class MediaInfoLoader:
    """show(item_id, info) is called (from another thread) when a title's MediaInfo arrives."""

    def __init__(self, client, show_info):
        self._client = client
        self._show = show_info
        self._known = {}
        self._timer = None

    def request(self, item_id):
        """The title's MediaInfo if it's known already; otherwise None, and it's asked for."""
        self.cancel()
        if item_id in self._known:
            return self._known[item_id]
        self._timer = threading.Timer(DELAY_SECONDS, self._fetch, (item_id,))
        self._timer.daemon = True
        self._timer.start()
        return None

    def cancel(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _fetch(self, item_id):
        try:
            data = self._client.get_item(item_id)
        except JellyfinError as error:
            log(f"Couldn't get the media details of {item_id}: {error}", xbmc.LOGWARNING)
            return
        source = versions.chosen_source(data)
        info = MediaInfo(media_summary(data, source), media_badges(data, source))
        self._known[item_id] = info
        self._show(item_id, info)

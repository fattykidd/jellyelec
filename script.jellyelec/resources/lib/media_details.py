"""The focused title's resolution and audio, such as "4K · Dolby Vision · Dolby TrueHD Atmos 7.1".

Jellyfin only describes a title's files (video and audio tracks) when asked about that one
title, so the screens ask once focus has rested on a poster for a moment. Scrolling past
posters then doesn't send a request for each one, and each title is asked about only once.
"""

import threading

import xbmc

from resources.lib import versions
from resources.lib.api import JellyfinError
from resources.lib.formatting import media_summary
from resources.lib.kodi import log

# How long focus must rest on a title before its details are asked for.
DELAY_SECONDS = 0.4


class MediaSummaryLoader:
    """show(item_id, summary) is called (from another thread) when a summary arrives."""

    def __init__(self, client, show):
        self._client = client
        self._show = show
        self._summaries = {}
        self._timer = None

    def request(self, item_id):
        """The title's summary if it's known already; otherwise None, and it's asked for."""
        self.cancel()
        if item_id in self._summaries:
            return self._summaries[item_id]
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
        summary = media_summary(data, versions.chosen_source(data))
        self._summaries[item_id] = summary
        self._show(item_id, summary)

"""Play an item through Kodi's player and keep Jellyfin up to date.

Kodi plays the original file streamed from the server (no transcoding), so
CoreELEC's Dolby Vision, FEL and audio passthrough handling all apply.
"""

import uuid

import xbmc
import xbmcgui

from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import format_time
from resources.lib.kodi import ADDON_NAME, log
from resources.lib.listitems import media_item

START_TIMEOUT_SECONDS = 30
PROGRESS_INTERVAL_SECONDS = 10


def play(client, data, start_seconds=None):
    """Play a movie, episode, trailer or extra. Returns once playback has finished.

    start_seconds: where to start. Leave it out to ask the user whether to resume.
    """
    if start_seconds is None:
        start_seconds = _ask_start_position(data)
        if start_seconds is None:
            return

    try:
        info = client.get_playback_info(data["Id"])
    except JellyfinError as error:
        log(f"Couldn't get playback info for {data['Id']}: {error}", xbmc.LOGWARNING)
        _notify("Couldn't get playback details from the server.")
        return

    sources = info.get("MediaSources") or []
    if not sources:
        _notify("The server has no playable file for this item.")
        return
    source = sources[0]

    session = PlaybackSession(
        client,
        item_id=data["Id"],
        media_source_id=source["Id"],
        play_session_id=info.get("PlaySessionId") or uuid.uuid4().hex,
    )
    url = client.stream_url(data["Id"], source["Id"], session.play_session_id, source.get("Container"))

    item = media_item(client, data)
    item.setPath(url)
    if start_seconds:
        item.setProperty("StartOffset", f"{start_seconds:.3f}")

    log(f"Playing {data.get('Name')} ({data['Id']}) from {format_time(start_seconds)}.")
    session.run(item, url, start_seconds)


class PlaybackSession:
    """One playback of one item: starts it, watches it, and reports to Jellyfin."""

    def __init__(self, client, item_id, media_source_id, play_session_id):
        self.client = client
        self.item_id = item_id
        self.media_source_id = media_source_id
        self.play_session_id = play_session_id
        self._player = xbmc.Player()
        self._monitor = xbmc.Monitor()

    def run(self, item, url, start_seconds):
        self._player.play(url, item)
        if not self._wait_for_start():
            _notify("Couldn't play this file.")
            return

        if not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")

        position = start_seconds
        self._report("start", position)
        position = self._watch(position)
        self._report("stopped", position)
        log(f"Playback stopped at {format_time(position)}.")

    def _wait_for_start(self):
        waited = 0.0
        while not self._player.isPlayingVideo():
            if self._monitor.waitForAbort(0.25):
                return False
            waited += 0.25
            if waited >= START_TIMEOUT_SECONDS:
                log("Playback didn't start in time.", xbmc.LOGWARNING)
                return False
        return True

    def _watch(self, position):
        """Report progress until playback ends. Returns the last known position in seconds."""
        was_paused = False
        since_report = 0
        while self._player.isPlayingVideo():
            try:
                position = self._player.getTime()
            except RuntimeError:
                break

            is_paused = xbmc.getCondVisibility("Player.Paused")
            if since_report >= PROGRESS_INTERVAL_SECONDS or is_paused != was_paused:
                self._report("progress", position, is_paused)
                since_report = 0
                was_paused = is_paused

            if self._monitor.waitForAbort(1):
                break
            since_report += 1
        return position

    def _report(self, event, position_seconds, is_paused=False):
        """Tell the server. A failed report is logged but never interrupts playback."""
        ticks = position_seconds * TICKS_PER_SECOND
        ids = (self.item_id, self.media_source_id, self.play_session_id)
        try:
            if event == "start":
                self.client.report_playback_start(*ids, ticks)
            elif event == "progress":
                self.client.report_playback_progress(*ids, ticks, is_paused)
            else:
                self.client.report_playback_stopped(*ids, ticks)
        except JellyfinError as error:
            log(f"Couldn't report playback {event}: {error}", xbmc.LOGWARNING)


# Helpers ------------------------------------------------------------------------

def _ask_start_position(data):
    """Offer to resume if there's a saved position. Returns seconds, or None if cancelled."""
    ticks = (data.get("UserData") or {}).get("PlaybackPositionTicks") or 0
    if not ticks:
        return 0
    seconds = ticks / TICKS_PER_SECOND
    choice = xbmcgui.Dialog().contextmenu([f"Resume from {format_time(seconds)}", "Play from beginning"])
    if choice < 0:
        return None
    return seconds if choice == 0 else 0


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

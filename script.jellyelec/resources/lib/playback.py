"""Play movies, episodes, trailers and extras through Kodi's player, and keep Jellyfin up to date.

Kodi plays the original file streamed from the server (no transcoding), so
CoreELEC's Dolby Vision, FEL and audio passthrough handling all apply.
"""

import uuid

import xbmc
import xbmcgui

from resources.lib import versions
from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.chapters import STOP, choose_chapter
from resources.lib.formatting import format_time
from resources.lib.kodi import log, notify
from resources.lib.listitems import media_item

START_TIMEOUT_SECONDS = 30
PROGRESS_INTERVAL_SECONDS = 10

# Playback is checked four times a second, so Back opens the chapter list promptly.
CHECK_SECONDS = 0.25
CHECKS_PER_SECOND = 4


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
        notify("Couldn't get playback details from the server.")
        return

    sources = info.get("MediaSources") or []
    if not sources:
        notify("The server has no playable file for this item.")
        return
    source = _pick_source(sources, data["Id"])

    session = PlaybackSession(
        client,
        data,
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


def _pick_source(sources, item_id):
    """The version picked on the details screen, or else the server's first."""
    remembered = versions.remembered_source_id(item_id)
    source = next((source for source in sources if source.get("Id") == remembered), sources[0])
    if len(sources) > 1:
        log(f"Playing version {source.get('Name') or source.get('Id')} of {len(sources)}.")
    return source


class PlaybackSession:
    """One playback of one item: starts it, watches it, and reports to Jellyfin."""

    def __init__(self, client, data, item_id, media_source_id, play_session_id):
        self.client = client
        self.data = data
        self.item_id = item_id
        self.media_source_id = media_source_id
        self.play_session_id = play_session_id
        self._player = xbmc.Player()
        self._monitor = xbmc.Monitor()

    def run(self, item, url, start_seconds):
        self._player.play(url, item)
        if not wait_for_video(self._player, self._monitor):
            notify("Couldn't play this file.")
            return

        position = start_seconds
        self._report("start", position)
        position = self._watch(position)
        self._report("stopped", position)
        log(f"Playback stopped at {format_time(position)}.")

    def _watch(self, position):
        """Report progress until playback ends. Returns the last known position in seconds."""
        was_paused = False
        checks_since_report = 0
        while self._player.isPlayingVideo():
            try:
                position = self._player.getTime()
            except RuntimeError:
                break

            if self._back_pressed():
                self._show_chapters(position)
                continue

            is_paused = xbmc.getCondVisibility("Player.Paused")
            if checks_since_report >= PROGRESS_INTERVAL_SECONDS * CHECKS_PER_SECOND or is_paused != was_paused:
                self._report("progress", position, is_paused)
                checks_since_report = 0
                was_paused = is_paused

            if self._monitor.waitForAbort(CHECK_SECONDS):
                break
            checks_since_report += 1
        return position

    # Back and the chapter list --------------------------------------------------------

    def _back_pressed(self):
        """True if Back took Kodi out of full-screen while the video is still playing.

        Watching for this, rather than for the key itself, works for every remote: the
        Unfolded Circle integration, for one, sends Back as a command that no key map sees.
        """
        if xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
            return False
        # At the end of a file Kodi leaves full-screen just before it stops; a moment's
        # wait tells that apart from Back.
        if self._monitor.waitForAbort(0.5):
            return False
        return self._player.isPlayingVideo() and not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)")

    def _show_chapters(self, position):
        go_fullscreen(self._monitor)
        choice = choose_chapter(self.client, self.data, position)
        if choice == STOP:
            log("Stopped from the chapter list.")
            self._player.stop()
        elif choice is not None:
            log(f"Jumping to the chapter at {format_time(choice)}.")
            self._player.seekTime(choice)

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

def wait_for_video(player, monitor, fullscreen=True):
    """Wait for video to start, then (unless told not to) make it full-screen.

    Returns False if it never starts.
    """
    waited = 0.0
    while not player.isPlayingVideo():
        if monitor.waitForAbort(0.25):
            return False
        waited += 0.25
        if waited >= START_TIMEOUT_SECONDS:
            log("Playback didn't start in time.", xbmc.LOGWARNING)
            return False
    if fullscreen:
        go_fullscreen(monitor)
    return True


def go_fullscreen(monitor, timeout_seconds=5):
    """Switch to full-screen video, retrying while Kodi refuses (it does while a busy dialog is up)."""
    waited = 0.0
    while not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
        if waited >= timeout_seconds:
            log("Couldn't switch to full-screen video.", xbmc.LOGWARNING)
            return
        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        if monitor.waitForAbort(0.5):
            return
        waited += 0.5


def stop_and_wait(player, monitor, timeout_seconds=5):
    """Stop playback and wait for it to finish, so the old connection closes before a new one opens."""
    player.stop()
    waited = 0.0
    while player.isPlaying() and waited < timeout_seconds:
        if monitor.waitForAbort(0.25):
            return
        waited += 0.25


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

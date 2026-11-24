"""Play items and Live TV channels through Kodi's player, and keep Jellyfin up to date.

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
        if not wait_for_video(self._player, self._monitor):
            _notify("Couldn't play this file.")
            return

        position = start_seconds
        self._report("start", position)
        position = self._watch(position)
        self._report("stopped", position)
        log(f"Playback stopped at {format_time(position)}.")

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


# Live TV ------------------------------------------------------------------------

DIRECT_URL_SCHEMES = ("http://", "https://", "rtmp://", "rtsp://", "udp://", "rtp://")


def direct_stream_url(channel):
    """The channel's original stream URL from your playlist, if Jellyfin shares it."""
    path = channel.get("Path") or ""
    return path if path.lower().startswith(DIRECT_URL_SCHEMES) else None


def play_channel(client, channels, index, make_item):
    """Play one channel full-screen.

    Channels with a direct stream URL are queued as a playlist so Next/Previous changes
    channel, and Kodi plays the provider's stream itself (like IPTV Simple does).
    Channels without one are tuned and relayed by Jellyfin instead.
    make_item(channel) builds the ListItem Kodi shows while the channel plays.
    """
    channel = channels[index]
    if direct_stream_url(channel):
        _play_channels_directly(channels, channel, make_item)
    else:
        _play_channel_through_jellyfin(client, channel, make_item)


def _play_channels_directly(channels, channel, make_item):
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    start_position = 0
    for candidate in channels:
        url = direct_stream_url(candidate)
        if not url:
            continue
        if candidate is channel:
            start_position = playlist.size()
        item = make_item(candidate)
        item.setPath(url)
        playlist.add(url, item)

    log(f"Live TV: playing {channel.get('Name')} directly from its stream URL "
        f"({playlist.size()} channels queued for Next/Previous).")
    player = xbmc.Player()
    player.play(playlist, startpos=start_position)
    if not wait_for_video(player, xbmc.Monitor()):
        _notify("Couldn't play this channel.")


def _play_channel_through_jellyfin(client, channel, make_item):
    log(f"Live TV: {channel.get('Name')} has no direct stream URL; asking Jellyfin to tune it.")
    try:
        info = client.open_live_stream(channel["Id"])
    except JellyfinError as error:
        log(f"Couldn't tune {channel.get('Name')}: {error}", xbmc.LOGWARNING)
        _notify("Couldn't tune this channel.")
        return

    sources = info.get("MediaSources") or []
    if not sources:
        _notify("The server couldn't tune this channel.")
        return
    source = sources[0]
    live_stream_id = source.get("LiveStreamId")
    play_session_id = info.get("PlaySessionId") or uuid.uuid4().hex
    url = client.stream_url(
        channel["Id"], source["Id"], play_session_id, source.get("Container"), live_stream_id
    )

    item = make_item(channel)
    item.setPath(url)
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    try:
        player.play(url, item)
        if not wait_for_video(player, monitor):
            _notify("Couldn't play this channel.")
            return
        while player.isPlayingVideo() and not monitor.waitForAbort(1):
            pass
    finally:
        if live_stream_id:
            try:
                client.close_live_stream(live_stream_id)
            except JellyfinError as error:
                log(f"Couldn't release live stream {live_stream_id}: {error}", xbmc.LOGWARNING)


# Helpers ------------------------------------------------------------------------

def wait_for_video(player, monitor):
    """Wait for video to start, then make sure it's full-screen. False if it never starts."""
    waited = 0.0
    while not player.isPlayingVideo():
        if monitor.waitForAbort(0.25):
            return False
        waited += 0.25
        if waited >= START_TIMEOUT_SECONDS:
            log("Playback didn't start in time.", xbmc.LOGWARNING)
            return False
    if not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
    return True


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

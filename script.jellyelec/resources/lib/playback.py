"""Play items and Live TV channels through Kodi's player, and keep Jellyfin up to date.

Kodi plays the original file streamed from the server (no transcoding), so
CoreELEC's Dolby Vision, FEL and audio passthrough handling all apply.
"""

import urllib.parse
import uuid

import xbmc
import xbmcgui

from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import format_time
from resources.lib.kodi import ADDON_NAME, log, setting_enabled
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

STREAM_SCHEMES = ("http://", "https://", "rtmp://", "rtsp://", "udp://", "rtp://")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def play_channel(client, channel, make_item):
    """Play one Live TV channel full-screen. Returns once it stops.

    make_item(channel) builds the ListItem Kodi shows while the channel plays.
    """
    name = channel.get("Name", channel["Id"])
    url, live_stream_id = _resolve_channel_stream(client, channel)
    if not url:
        log(f"Live TV: no playable stream for {name}.", xbmc.LOGWARNING)
        _notify("Couldn't play this channel.")
        _release_live_stream(client, live_stream_id)
        return

    item = make_item(channel)
    item.setPath(url)
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    try:
        player.play(url, item)
        if not wait_for_video(player, monitor):
            _notify("Couldn't play this channel.")
            return
        # Keep the tuned stream open on the server until playback stops.
        while live_stream_id and player.isPlayingVideo() and not monitor.waitForAbort(1):
            pass
    finally:
        _release_live_stream(client, live_stream_id)


def _resolve_channel_stream(client, channel):
    """Work out what Kodi should play for a channel.

    Returns (url, live_stream_id). live_stream_id is set when Jellyfin tuned the channel
    for us, and must be released when playback ends.
    """
    name = channel.get("Name", channel["Id"])

    # 1. The provider's own stream URL, played directly the way IPTV Simple does.
    #    Skipped when the user has chosen to play Live TV through Jellyfin.
    if setting_enabled("livetv_through_jellyfin"):
        log(f"Live TV: {name}: set to play through Jellyfin.")
    else:
        try:
            info = client.get_playback_info(channel["Id"])
            source = (info.get("MediaSources") or [{}])[0]
        except JellyfinError as error:
            log(f"Live TV: {name}: couldn't get playback details: {error}", xbmc.LOGWARNING)
            source = {}
        log(f"Live TV: {name}: before tuning, server offers {_describe_source(source)}.")
        path = source.get("Path") or ""
        if _is_stream_url(path) and not _points_at_server(client, path):
            log(f"Live TV: {name}: playing the provider's stream directly.")
            return _with_required_headers(path, source), None

    # 2. Jellyfin tunes the channel and relays it.
    try:
        info = client.open_live_stream(channel["Id"])
        source = (info.get("MediaSources") or [{}])[0]
    except JellyfinError as error:
        log(f"Live TV: {name}: couldn't tune: {error}", xbmc.LOGWARNING)
        return None, None
    log(f"Live TV: {name}: after tuning, server offers {_describe_source(source)}.")
    live_stream_id = source.get("LiveStreamId")

    path = source.get("Path") or ""
    if _is_stream_url(path):
        log(f"Live TV: {name}: playing Jellyfin's relayed stream.")
        return _reachable_url(client, path), live_stream_id

    # 3. Jellyfin's repackaged (HLS) stream, as its other clients use.
    if source.get("TranscodingUrl"):
        log(f"Live TV: {name}: playing Jellyfin's repackaged stream.")
        return client.server_url + source["TranscodingUrl"], live_stream_id

    return None, live_stream_id


def _with_required_headers(url, source):
    """Add any request headers the stream needs (such as a User-Agent), in Kodi's URL|Header=value form."""
    headers = source.get("RequiredHttpHeaders") or {}
    if not headers:
        return url
    log(f"Live TV: sending the headers the stream requires: {', '.join(sorted(headers))}.")
    encoded = "&".join(f"{name}={urllib.parse.quote(value)}" for name, value in headers.items())
    return f"{url}|{encoded}"


def _release_live_stream(client, live_stream_id):
    if not live_stream_id:
        return
    try:
        client.close_live_stream(live_stream_id)
    except JellyfinError as error:
        log(f"Couldn't release live stream: {error}", xbmc.LOGWARNING)


def _is_stream_url(path):
    return path.lower().startswith(STREAM_SCHEMES)


def _points_at_server(client, url):
    """True for URLs on the Jellyfin server itself (including its loopback address)."""
    host = urllib.parse.urlsplit(url).hostname or ""
    return host in LOOPBACK_HOSTS or host == urllib.parse.urlsplit(client.server_url).hostname


def _reachable_url(client, url):
    """Make a server URL usable from this box: fix a loopback host and add the sign-in token."""
    if not _points_at_server(client, url):
        return url
    parts = urllib.parse.urlsplit(url)
    server = urllib.parse.urlsplit(client.server_url)
    query = urllib.parse.parse_qs(parts.query)
    if "api_key" not in query and "ApiKey" not in query:
        separator = "&" if parts.query else ""
        parts = parts._replace(query=f"{parts.query}{separator}api_key={client.token}")
    return urllib.parse.urlunsplit(parts._replace(scheme=server.scheme, netloc=server.netloc))


def _describe_source(source):
    """A log-safe summary of a media source: no tokens, passwords or query strings."""
    if not source:
        return "nothing"
    path = source.get("Path") or ""
    if _is_stream_url(path):
        parts = urllib.parse.urlsplit(path)
        path = f"{parts.scheme}://{parts.hostname}/…"
    return (
        f"protocol={source.get('Protocol')}, path={path or 'none'}, "
        f"direct play={source.get('SupportsDirectPlay')}, "
        f"direct stream={source.get('SupportsDirectStream')}, "
        f"repackaged={'yes' if source.get('TranscodingUrl') else 'no'}, "
        f"tuned={'yes' if source.get('LiveStreamId') else 'no'}"
    )


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

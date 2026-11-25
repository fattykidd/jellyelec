"""Live TV playback: channel switching, the stall watchdog, and finding each channel's stream.

When a channel is played, every channel is queued as a Kodi playlist entry that points
back at JellyELEC (plugin://script.jellyelec/?channel=...). Kodi only asks for a channel's
real stream address when that channel is actually played (see channel_resolver.py), so
changing channel only ever has one stream open at a time.
"""

import json
import threading
import traceback
import urllib.parse

import xbmc
import xbmcgui

from resources.lib.api import JellyfinError
from resources.lib.key_requests import (
    CHANNEL_DOWN_REQUEST,
    CHANNEL_UP_REQUEST,
    GUIDE_REQUEST,
    clear_requests,
    take_request,
)
from resources.lib.kodi import ADDON_ID, log, notify
from resources.lib.playback import go_fullscreen, stop_and_wait, wait_for_video

# Watchdog: a channel whose picture hasn't moved for this long is reconnected, up to
# MAX_RECONNECTS times in a row before giving up. A minute of smooth playback resets the count.
STALL_SECONDS = 10
MAX_RECONNECTS = 3
SMOOTH_SECONDS_TO_RESET = 60

# Pause between closing a stalled connection and opening a new one, so the provider
# has counted the old one as closed (it may limit how many streams you can have open).
RECONNECT_PAUSE_SECONDS = 3

# How long full-screen video may be out of view (with the guide closed) before it
# counts as Back = stop.
LEFT_FULLSCREEN_SECONDS = 1

# After asking Kodi to step out of full-screen into the guide, how long to wait for it
# to actually happen before giving up on the guide.
GUIDE_OPEN_TIMEOUT_SECONDS = 2

# The background thread checks for key presses this often, and runs the once-a-second
# checks every TICKS_PER_SECOND ticks.
TICK_SECONDS = 0.25
TICKS_PER_SECOND = 4

# How long to wait for the next channel to start after Next/Previous.
CHANNEL_CHANGE_TIMEOUT_SECONDS = 20

# Kodi's stream reader for live TV, as IPTV Simple can use. Used when it's installed.
FFMPEG_DIRECT = "inputstream.ffmpegdirect"
TS_CONTAINERS = {"ts", "mpegts", "m2ts"}

# Where the resolver leaves the ID of a channel Jellyfin tuned for us, so the watchdog
# can release it. Kept on Kodi's Home window, which both parts of JellyELEC can see.
LIVE_STREAM_PROPERTY = f"{ADDON_ID}.live_stream_id"
HOME_WINDOW_ID = 10000

# Kodi's ID for the video playlist, as used by its JSON-RPC interface.
VIDEO_PLAYLIST_ID = 1

STREAM_SCHEMES = ("http://", "https://", "rtmp://", "rtsp://", "udp://", "rtp://")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


# Watching Live TV ---------------------------------------------------------------------

class LiveSession:
    """One Live TV viewing session.

    start() queues every channel as a playlist and plays one. A background thread then
    stays with playback until it stops: it follows channel changes, reconnects a channel
    whose picture stops moving, answers Guide and Channel Up/Down key presses, and stops
    playback when the user presses Back out of full-screen. Running in the background
    keeps the Live TV screen responsive, so it can work as the guide over the live picture.

    on_channel_changed(position) and on_finished(position) are called from the
    background thread.
    """

    def __init__(self, client, channels, make_item, on_channel_changed=None, on_finished=None):
        self.client = client
        self.channels = channels
        self.make_item = make_item
        self.on_channel_changed = on_channel_changed
        self.on_finished = on_finished
        self.position = 0
        self.in_guide = False
        self._player = xbmc.Player()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    # Controls, used by the Live TV screen ---------------------------------------------

    def start(self, index):
        """Play channels[index] full-screen, with the other channels queued around it."""
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        for channel in self.channels:
            url = channel_url(channel)
            item = self.make_item(channel)
            item.setPath(url)
            item.setProperty("IsPlayable", "true")
            playlist.add(url, item)

        self.position = index
        self.in_guide = False
        clear_requests()
        self._player.play(playlist, startpos=index)
        self._thread = threading.Thread(target=self._run, name="JellyELEC Live TV", daemon=True)
        self._thread.start()

    def switch_to(self, index):
        """Change channel without leaving the guide."""
        if index != self.position:
            play_playlist_position(index)

    def show_fullscreen(self):
        """Close the guide and return to full-screen video."""
        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")

    def stop(self):
        self._player.stop()

    # Background thread ----------------------------------------------------------------

    def _run(self):
        # Kodi objects used on this thread are created on it.
        self._thread_player = xbmc.Player()
        self._playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        self._monitor = xbmc.Monitor()
        try:
            if not wait_for_video(self._thread_player, self._monitor):
                notify("Couldn't play this channel.")
                return
            # Next/Previous (and Kodi's own skip keys) wrap around the channel list.
            xbmc.executebuiltin("PlayerControl(RepeatAll)")
            self._reset_channel_state()
            tick = 0
            while not self._monitor.waitForAbort(TICK_SECONDS):
                self._handle_key_request()
                tick += 1
                if tick % TICKS_PER_SECOND == 0 and not self._check_once_a_second():
                    break
                if not self._check_fullscreen():
                    break
        except Exception:
            # An error here would otherwise end the thread silently, leaving the keys,
            # the watchdog and Back = stop all quietly doing nothing.
            log(f"Live TV: the session stopped on an unexpected error:\n{traceback.format_exc()}", xbmc.LOGERROR)
            notify("Live TV hit an error. Details are in the log.")
        finally:
            _release_tuned_stream(self.client)
            clear_requests()
            if self.on_finished:
                self.on_finished(self.position)

    def _check_once_a_second(self):
        """Channel changes and the stall watchdog. False once playback has ended."""
        player = self._thread_player
        if not player.isPlayingVideo():
            return self._followed_channel_change()
        if self._playlist.getposition() not in (self.position, -1):
            self._on_channel_changed()
        if self._stalled():
            return self._reconnect()
        return True

    # Key presses from the key map -----------------------------------------------------

    def _handle_key_request(self):
        request = take_request()
        if not request or not self._thread_player.isPlayingVideo():
            return
        if request == GUIDE_REQUEST:
            if xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
                log("Live TV: opening the guide.")
                self.in_guide = True
                # Kodi leaves full-screen a moment after being asked; until it has,
                # still being full-screen doesn't mean the guide was closed.
                self.guide_opening_ticks = 1
                # Stepping back out of full-screen lands on the Live TV screen,
                # which shows itself as the guide while a channel is playing.
                xbmc.executebuiltin("Action(Back)")
        elif request == CHANNEL_UP_REQUEST:
            self._change_channel_by(1)
        elif request == CHANNEL_DOWN_REQUEST:
            self._change_channel_by(-1)

    def _change_channel_by(self, step):
        """Channel Up/Down, wrapping around at either end of the list."""
        if self.channels:
            play_playlist_position((self.position + step) % len(self.channels))

    # Back = stop, unless the guide is open --------------------------------------------

    def _check_fullscreen(self):
        """False once the user has pressed Back out of full-screen (and not into the guide)."""
        fullscreen = xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)")
        if self.in_guide:
            self.out_of_view_ticks = 0
            if self.guide_opening_ticks:
                if not fullscreen:
                    self.guide_opening_ticks = 0  # the guide is showing now
                elif self.guide_opening_ticks * TICK_SECONDS >= GUIDE_OPEN_TIMEOUT_SECONDS:
                    self.in_guide = False  # Kodi never left full-screen
                    self.guide_opening_ticks = 0
                else:
                    self.guide_opening_ticks += 1
            elif fullscreen:
                self.in_guide = False  # the guide was closed
            return True
        if fullscreen or not self._thread_player.isPlayingVideo():
            self.out_of_view_ticks = 0
            return True
        self.out_of_view_ticks += 1
        if self.out_of_view_ticks * TICK_SECONDS < LEFT_FULLSCREEN_SECONDS:
            return True
        log(f"Live TV: {self._name()}: left full-screen; stopping.")
        self._thread_player.stop()
        return False

    # Channel changes --------------------------------------------------------------

    def _followed_channel_change(self):
        """Playback isn't running. True if that's another channel starting."""
        player = self._thread_player
        playlist = self._playlist
        waited = 0.0
        while waited < CHANNEL_CHANGE_TIMEOUT_SECONDS:
            if player.isPlayingVideo():
                if playlist.getposition() != self.position:
                    self._on_channel_changed()
                if not self.in_guide:
                    go_fullscreen(self._monitor)
                return True
            # Same channel (or none, which is what Kodi reports once a playlist stops)
            # and nothing loading after a moment: the user stopped playback.
            if waited >= 1.5 and playlist.getposition() in (self.position, -1):
                return False
            if self._monitor.waitForAbort(0.5):
                return False
            waited += 0.5
        log("Live TV: the next channel didn't start in time.", xbmc.LOGWARNING)
        return False

    def _on_channel_changed(self):
        self.position = self._playlist.getposition()
        _release_tuned_stream(self.client)
        self._reset_channel_state()
        log(f"Live TV: changed channel to {self._name()}.")
        if self.on_channel_changed:
            self.on_channel_changed(self.position)

    # Stall watchdog -----------------------------------------------------------------

    def _stalled(self):
        """True once the picture has been still (and not paused) for STALL_SECONDS."""
        try:
            current_time = self._thread_player.getTime()
        except RuntimeError:
            return False
        moving = current_time > self.last_time if self.last_time is not None else True
        if moving or xbmc.getCondVisibility("Player.Paused"):
            self.still_seconds = 0
            self.smooth_seconds += 1
            if self.smooth_seconds >= SMOOTH_SECONDS_TO_RESET:
                self.reconnects = 0
        else:
            self.still_seconds += 1
            self.smooth_seconds = 0
        self.last_time = current_time
        return self.still_seconds >= STALL_SECONDS

    def _reconnect(self):
        """Reopen the current channel. False if it gave up or the channel wouldn't restart."""
        name = self._name()
        player = self._thread_player
        if self.reconnects >= MAX_RECONNECTS:
            log(f"Live TV: {name}: still stalled after {MAX_RECONNECTS} reconnects; giving up.", xbmc.LOGWARNING)
            player.stop()
            notify("This channel keeps stalling. Try again in a minute.")
            return False

        self.reconnects += 1
        log(f"Live TV: {name}: stalled for {STALL_SECONDS} seconds; reconnecting ({self.reconnects} of {MAX_RECONNECTS}).")
        in_guide = self.in_guide
        stop_and_wait(player, self._monitor)
        _release_tuned_stream(self.client)
        if self._monitor.waitForAbort(RECONNECT_PAUSE_SECONDS):
            return False
        play_playlist_position(self.position)
        if not wait_for_video(player, self._monitor, fullscreen=not in_guide):
            notify("Couldn't reconnect to this channel.")
            return False
        self.in_guide = in_guide
        self.last_time = None
        self.still_seconds = 0
        self.out_of_view_ticks = 0
        return True

    # Helpers ------------------------------------------------------------------------

    def _reset_channel_state(self):
        self.guide_opening_ticks = 0
        self.reconnects = 0
        self.last_time = None
        self.still_seconds = 0
        self.smooth_seconds = 0
        self.out_of_view_ticks = 0

    def _name(self):
        if 0 <= self.position < len(self.channels):
            return self.channels[self.position].get("Name", "")
        return "channel"


def play_playlist_position(position):
    """Play one entry of Kodi's video playlist.

    Done through Kodi's JSON-RPC interface because it names the video playlist outright.
    Player.playselected() can't be used here: a Player object other than the one that
    started the playlist assumes the music playlist, so it would switch Kodi to that
    (empty) playlist instead, which also breaks Kodi's own Next/Previous keys.
    """
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Player.Open",
        "params": {"item": {"playlistid": VIDEO_PLAYLIST_ID, "position": position}},
    }
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        log(f"Live TV: Kodi couldn't play playlist entry {position}: {response['error']}", xbmc.LOGWARNING)


def channel_url(channel):
    """The playlist address for a channel; Kodi hands it back to JellyELEC when it's played."""
    query = urllib.parse.urlencode({"channel": channel["Id"], "name": channel.get("Name", "")})
    return f"plugin://{ADDON_ID}/?{query}"


# Finding a channel's stream -----------------------------------------------------------

def resolve_channel_stream(client, channel):
    """Work out what Kodi should play for a channel.

    Returns (url, live_stream_id, container). live_stream_id is set when Jellyfin tuned
    the channel for us, and must be released when playback ends. container is the stream
    type Jellyfin reports, such as "ts".
    """
    name = channel.get("Name") or channel["Id"]

    # 1. The provider's own stream URL, played directly the way IPTV Simple does.
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
        return _with_required_headers(path, source), None, source.get("Container")

    # 2. Jellyfin tunes the channel and relays it.
    try:
        info = client.open_live_stream(channel["Id"])
        source = (info.get("MediaSources") or [{}])[0]
    except JellyfinError as error:
        log(f"Live TV: {name}: couldn't tune: {error}", xbmc.LOGWARNING)
        return None, None, None
    log(f"Live TV: {name}: after tuning, server offers {_describe_source(source)}.")
    live_stream_id = source.get("LiveStreamId")

    path = source.get("Path") or ""
    if _is_stream_url(path) and not _points_at_server(client, path):
        # Tuning just handed back the provider's own URL. Release Jellyfin's connection
        # so the provider never sees two at once, and play the URL directly.
        release_live_stream(client, live_stream_id)
        log(f"Live TV: {name}: tuning returned the provider's stream; playing it directly.")
        return _with_required_headers(path, source), None, source.get("Container")
    if _is_stream_url(path):
        log(f"Live TV: {name}: playing Jellyfin's relayed stream.")
        return _reachable_url(client, path), live_stream_id, source.get("Container")

    # 3. Jellyfin's repackaged (HLS) stream, as its other clients use.
    if source.get("TranscodingUrl"):
        log(f"Live TV: {name}: playing Jellyfin's repackaged stream.")
        return client.server_url + source["TranscodingUrl"], live_stream_id, None

    return None, live_stream_id, None


def prepare_live_item(item, container):
    """Tell Kodi up front what the stream is, so it doesn't make an extra request to find out.

    Uses inputstream.ffmpegdirect when it's installed, as IPTV Simple can.
    """
    item.setContentLookup(False)
    if (container or "").lower() in TS_CONTAINERS:
        item.setMimeType("video/mp2t")
    if xbmc.getCondVisibility(f"System.HasAddon({FFMPEG_DIRECT})"):
        item.setProperty("inputstream", FFMPEG_DIRECT)
        item.setProperty(f"{FFMPEG_DIRECT}.is_realtime_stream", "true")
        log(f"Live TV: playing with {FFMPEG_DIRECT}.")
    else:
        log("Live TV: playing with Kodi's built-in stream reader.")


def remember_tuned_stream(live_stream_id):
    """Note a channel Jellyfin tuned for us, so the watchdog releases it when it's done."""
    _home().setProperty(LIVE_STREAM_PROPERTY, live_stream_id or "")


def release_live_stream(client, live_stream_id):
    if not live_stream_id:
        return
    try:
        client.close_live_stream(live_stream_id)
    except JellyfinError as error:
        log(f"Couldn't release live stream: {error}", xbmc.LOGWARNING)


def _release_tuned_stream(client):
    """Release the channel Jellyfin last tuned for us, if any."""
    home = _home()
    live_stream_id = home.getProperty(LIVE_STREAM_PROPERTY)
    if live_stream_id:
        home.clearProperty(LIVE_STREAM_PROPERTY)
        release_live_stream(client, live_stream_id)


def _home():
    return xbmcgui.Window(HOME_WINDOW_ID)


# Stream address helpers -----------------------------------------------------------------

def _with_required_headers(url, source):
    """Add any request headers the stream needs (such as a User-Agent), in Kodi's URL|Header=value form."""
    headers = source.get("RequiredHttpHeaders") or {}
    if not headers:
        return url
    log(f"Live TV: sending the headers the stream requires: {', '.join(sorted(headers))}.")
    encoded = "&".join(f"{name}={urllib.parse.quote(value)}" for name, value in headers.items())
    return f"{url}|{encoded}"


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

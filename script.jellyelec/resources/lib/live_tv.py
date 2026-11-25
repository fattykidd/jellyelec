"""The Live TV screen: channel list with what's on now and next.

While a channel is playing, the same screen works as the guide: the live picture shrinks
into a corner (top right by default, or top left), the list stays browsable, and picking
another channel switches the picture right there.
"""

from datetime import datetime, timedelta, timezone

import xbmc
import xbmcgui

from resources.lib.api import JellyfinError
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log, setting
from resources.lib.listitems import channel_item
from resources.lib.live_playback import FFMPEG_DIRECT, LiveSession

# Control IDs, matching jellyelec-livetv.xml.
CHANNEL_LIST = 700

# How far ahead to look for each channel's next programme.
GUIDE_LOOKAHEAD = timedelta(hours=6)

# The setting that puts the guide's live picture in the top-left corner instead of top-right.
VIDEO_CORNER_SETTING = "guide_video_corner"
TOP_LEFT = "Top left"

# The setting for what OK on another channel does in the guide: watch it full-screen
# (the default), or preview it in the corner with a second OK for full-screen.
GUIDE_OK_SETTING = "guide_ok_action"
PREVIEW_IN_CORNER = "Preview in the corner"

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def show_live_tv(client):
    """Open the Live TV screen. Returns when the user goes back."""
    _check_ffmpeg_direct()
    window = LiveTvWindow("jellyelec-livetv.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.doModal()
    del window


# Only offered once each time JellyELEC runs, so saying "Not now" isn't met with the same
# question every time Live TV opens.
_ffmpeg_direct_offered = False


def _check_ffmpeg_direct():
    """Offer to install or turn on FFmpeg Direct, which keeps live streams from stalling."""
    global _ffmpeg_direct_offered
    if _ffmpeg_direct_offered or xbmc.getCondVisibility(f"System.AddonIsEnabled({FFMPEG_DIRECT})"):
        return
    _ffmpeg_direct_offered = True

    installed = xbmc.getCondVisibility(f"System.HasAddon({FFMPEG_DIRECT})")
    problem = "is turned off" if installed else "isn't installed"
    log(f"Live TV: {FFMPEG_DIRECT} {problem}.", xbmc.LOGWARNING)
    fix = xbmcgui.Dialog().yesno(
        ADDON_NAME,
        f"Live TV uses Kodi's FFmpeg Direct add-on to keep channels playing smoothly, and it {problem}.[CR]"
        "Without it, channels may stall.",
        nolabel="Not now",
        yeslabel="Turn it on" if installed else "Install it",
    )
    if not fix:
        return
    if installed:
        xbmc.executebuiltin(f"EnableAddon({FFMPEG_DIRECT})", True)
    else:
        # Kodi asks to confirm, then installs it from the CoreELEC add-on repository.
        xbmc.executebuiltin(f"InstallAddon({FFMPEG_DIRECT})", True)


class LiveTvWindow(xbmcgui.WindowXML):
    """Set client before calling doModal()."""

    client = None

    _loaded = False
    _channels = ()
    _next_programs = None  # {channel ID: Jellyfin data for its next programme}
    _session = None  # the LiveSession while a channel is playing
    _closing = False  # set when Back in the guide leaves Live TV

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        # Read every time the screen shows, so a changed corner setting applies straight away.
        self.setProperty("video_left", "true" if setting(VIDEO_CORNER_SETTING) == TOP_LEFT else "")
        # onInit also runs whenever playback hands the screen back, so only the first
        # one loads anything.
        if not self._loaded:
            self._loaded = True
            self._load()

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            # From the guide, Back stops the channel and leaves Live TV in one go.
            # (OK on the playing channel is how to go back to full-screen.)
            self._closing = True
            if self._watching():
                self._session.stop()
            self.close()
        elif self.getFocusId() == CHANNEL_LIST:
            self._update_panel()

    def onClick(self, control_id):
        if control_id != CHANNEL_LIST:
            return
        position = self.getControl(CHANNEL_LIST).getSelectedPosition()
        if not 0 <= position < len(self._channels):
            return

        if self._watching():
            # In the guide: OK on the playing channel returns to full-screen; OK on another
            # channel switches to it, full-screen or in the corner as the setting says.
            if position == self._session.position:
                self._session.show_fullscreen()
            else:
                watch_fullscreen = setting(GUIDE_OK_SETTING) != PREVIEW_IN_CORNER
                self._session.switch_to(position, fullscreen=watch_fullscreen)
            return

        session = LiveSession(self.client, self._channels, self._make_item)
        session.on_channel_changed = self._mark_playing
        session.on_finished = lambda last_position: self._on_session_finished(session, last_position)
        self._session = session
        self._mark_playing(position)
        session.start(position)

    # Watching ---------------------------------------------------------------------

    def _watching(self):
        return self._session is not None and self._session.running

    def _mark_playing(self, position):
        """Highlight the channel that's playing (None for none). Called from the session's thread."""
        if self._closing:
            return
        channel_list = self.getControl(CHANNEL_LIST)
        for index in range(channel_list.size()):
            channel_list.getListItem(index).setProperty("playing", "true" if index == position else "")

    def _on_session_finished(self, session, last_position):
        """Playback stopped. Called from the session's thread."""
        if session is not self._session or self._closing:
            return
        self._session = None
        self._mark_playing(None)
        # What's on has probably moved on, so refresh, landing on the last channel watched.
        self._load(keep_position=last_position)

    # Loading --------------------------------------------------------------------

    def _load(self, keep_position=0):
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            self._channels = self.client.get_channels()
            self._next_programs = self._fetch_next_programs()
        except JellyfinError as error:
            log(f"Couldn't load Live TV: {error}", xbmc.LOGWARNING)
            xbmcgui.Dialog().notification(ADDON_NAME, "Couldn't load Live TV.", xbmcgui.NOTIFICATION_WARNING)
            self._channels, self._next_programs = [], {}
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

        log(f"Live TV: {len(self._channels)} channels.")

        channel_list = self.getControl(CHANNEL_LIST)
        channel_list.reset()
        channel_list.addItems([self._make_item(channel) for channel in self._channels])
        if not self._channels:
            return

        # Kodi applies selectItem a moment later, so pass the position on rather than reading it back.
        position = min(max(keep_position, 0), len(self._channels) - 1)
        channel_list.selectItem(position)
        self.setFocusId(CHANNEL_LIST)
        self._update_panel(position)

    def _fetch_next_programs(self):
        """Each channel's next programme, keyed by channel ID."""
        if not self._channels:
            return {}
        now = datetime.now(timezone.utc)
        programs = self.client.get_upcoming_programs(
            [channel["Id"] for channel in self._channels],
            start=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end=(now + GUIDE_LOOKAHEAD).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        next_programs = {}
        for program in programs:  # earliest first, so keep the first one per channel
            next_programs.setdefault(program.get("ChannelId"), program)
        return next_programs

    def _make_item(self, channel):
        next_program = self._next_programs.get(channel["Id"]) if self._next_programs else None
        return channel_item(self.client, channel, next_program, datetime.now(timezone.utc))

    # Details panel ----------------------------------------------------------------

    def _update_panel(self, position=None):
        """Show a channel's current programme in detail on the right.

        position: which channel to show. Leave it out to use the one highlighted in the list.
        """
        channel_list = self.getControl(CHANNEL_LIST)
        if position is None:
            position = channel_list.getSelectedPosition()
        if not 0 <= position < len(self._channels):
            return
        channel = self._channels[position]
        item = channel_list.getListItem(position)
        current = channel.get("CurrentProgram") or {}

        self.setProperty("channel_name", channel.get("Name", ""))
        self.setProperty("channel_logo", item.getArt("thumb"))
        self.setProperty("now_title", item.getProperty("now_title"))
        self.setProperty("now_episode", current.get("EpisodeTitle", ""))
        self.setProperty("now_time", item.getProperty("now_time"))
        self.setProperty("now_plot", current.get("Overview", ""))
        next_title = item.getProperty("next_title")
        next_time = item.getProperty("next_time")
        self.setProperty("next_line", f"Next: {next_title}  ·  {next_time}" if next_title else "")

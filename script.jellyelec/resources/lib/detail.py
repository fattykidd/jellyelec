"""The detail page for a movie or episode: info, play buttons, trailer and special features."""

import xbmc
import xbmcgui

from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import episode_line, format_time, media_summary, meta_line
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import backdrop_url, extra_item, poster_url
from resources.lib.playback import play

# Control IDs, matching jellyelec-detail.xml.
ACTION_BUTTONS = 300
SPECIAL_FEATURES_ROW = 400

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# What each action button does.
RESUME = "resume"
PLAY = "play"
TRAILER = "trailer"


def show_details(client, item_id):
    """Open the detail page for one item. Returns when the user goes back."""
    window = DetailWindow("jellyelec-detail.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.item_id = item_id
    window.doModal()
    del window


class DetailWindow(xbmcgui.WindowXML):
    """Set client and item_id before calling doModal()."""

    client = None
    item_id = None

    _loaded = False
    _item = None
    _trailers = ()
    _extras = None  # Jellyfin data for the special features, keyed by item ID

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        # onInit runs again after playback or a dialog; load only once.
        if self._loaded:
            return
        self._loaded = True
        if not self._load():
            self.close()

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()

    def onClick(self, control_id):
        if control_id == ACTION_BUTTONS:
            self._run_selected_action()
        elif control_id == SPECIAL_FEATURES_ROW:
            self._play_selected_extra()

    # Loading --------------------------------------------------------------------

    def _load(self):
        """Fetch everything the page shows. Returns False if the item couldn't be loaded."""
        try:
            self._item = self.client.get_item(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load item {self.item_id}: {error}", xbmc.LOGWARNING)
            _notify("Couldn't load the details for this item.")
            return False

        self._trailers = self._fetch_trailers()
        self._show_item()
        self._show_actions()
        self._show_special_features()
        self.setFocusId(ACTION_BUTTONS)
        return True

    def _fetch_trailers(self):
        if not self._item.get("LocalTrailerCount"):
            return []
        try:
            return self.client.get_local_trailers(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load trailers for {self.item_id}: {error}", xbmc.LOGWARNING)
            return []

    def _show_item(self):
        item = self._item
        is_episode = item.get("Type") == "Episode"
        self.setProperty("show_title", item.get("SeriesName", "") if is_episode else "")
        self.setProperty("title", item.get("Name", ""))
        self.setProperty("episode", episode_line(item))
        self.setProperty("meta", meta_line(item))
        self.setProperty("genres", ", ".join((item.get("Genres") or [])[:3]))
        self.setProperty("media", media_summary(item))
        self.setProperty("plot", item.get("Overview", ""))
        self.setProperty("poster", poster_url(self.client, item) or "")
        self.setProperty("backdrop", backdrop_url(self.client, item) or "")

    def _show_actions(self):
        resume_ticks = (self._item.get("UserData") or {}).get("PlaybackPositionTicks") or 0
        actions = []
        if resume_ticks:
            actions.append((RESUME, f"Resume from {format_time(resume_ticks / TICKS_PER_SECOND)}"))
            actions.append((PLAY, "Play from beginning"))
        else:
            actions.append((PLAY, "Play"))
        if self._trailers:
            actions.append((TRAILER, "Trailer"))

        buttons = self.getControl(ACTION_BUTTONS)
        buttons.reset()
        for action, label in actions:
            button = xbmcgui.ListItem(label=label, offscreen=True)
            button.setProperty("action", action)
            buttons.addItem(button)

    def _show_special_features(self):
        try:
            extras = self.client.get_special_features(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load special features for {self.item_id}: {error}", xbmc.LOGWARNING)
            extras = []

        self._extras = {extra["Id"]: extra for extra in extras}
        fallback = backdrop_url(self.client, self._item)
        row = self.getControl(SPECIAL_FEATURES_ROW)
        row.reset()
        row.addItems([extra_item(self.client, extra, fallback) for extra in extras])

    # Playback -------------------------------------------------------------------

    def _run_selected_action(self):
        selected = self.getControl(ACTION_BUTTONS).getSelectedItem()
        if selected is None:
            return
        action = selected.getProperty("action")

        if action == TRAILER:
            play(self.client, self._trailers[0], start_seconds=0)
            return

        if action == RESUME:
            ticks = (self._item.get("UserData") or {}).get("PlaybackPositionTicks") or 0
            play(self.client, self._item, start_seconds=ticks / TICKS_PER_SECOND)
        else:
            play(self.client, self._item, start_seconds=0)
        self._refresh_after_playback()

    def _play_selected_extra(self):
        selected = self.getControl(SPECIAL_FEATURES_ROW).getSelectedItem()
        if selected is None:
            return
        data = self._extras.get(selected.getProperty("id"))
        if data is not None:
            play(self.client, data, start_seconds=0)

    def _refresh_after_playback(self):
        """Update the resume button with the new position."""
        try:
            self._item = self.client.get_item(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't refresh item {self.item_id}: {error}", xbmc.LOGWARNING)
            return
        self._show_actions()
        self.setFocusId(ACTION_BUTTONS)


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

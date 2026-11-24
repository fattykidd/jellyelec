"""The detail page for a movie, episode or show: info, play buttons, trailer and special features."""

import xbmc
import xbmcgui

from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import episode_line, format_time, media_summary, meta_line
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import backdrop_url, extra_item, poster_url, season_item
from resources.lib.playback import play

# Control IDs, matching jellyelec-detail.xml.
ACTION_BUTTONS = 300
SPECIAL_FEATURES_ROW = 400
SEASONS_ROW = 410

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# What each action button does.
RESUME = "resume"
PLAY = "play"
NEXT_EPISODE = "next_episode"
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
    _next_episode = None  # for shows: the episode Play next episode starts
    _trailers = ()
    _extras = None  # Jellyfin data for the special features, keyed by item ID
    _seasons = None  # for shows: Jellyfin data for the seasons, keyed by item ID

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
        elif control_id == SEASONS_ROW:
            self._open_selected_season()

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
        self._show_seasons()
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
        if self._item.get("Type") == "Series":
            actions = self._series_actions()
        else:
            actions = self._video_actions()
        if self._trailers:
            actions.append((TRAILER, "Trailer"))

        buttons = self.getControl(ACTION_BUTTONS)
        buttons.reset()
        for action, label in actions:
            button = xbmcgui.ListItem(label=label, offscreen=True)
            button.setProperty("action", action)
            buttons.addItem(button)

    def _series_actions(self):
        """A show gets one button: the next episode to watch, or the first one if it's unstarted."""
        try:
            self._next_episode = (
                self.client.get_next_up(self.item_id)
                or self.client.get_first_episode(self.item_id)
            )
        except JellyfinError as error:
            log(f"Couldn't find the next episode of {self.item_id}: {error}", xbmc.LOGWARNING)
            self._next_episode = None
        if not self._next_episode:
            return []

        season = self._next_episode.get("ParentIndexNumber")
        episode = self._next_episode.get("IndexNumber")
        if season is not None and episode is not None:
            return [(NEXT_EPISODE, f"Play S{season} E{episode}")]
        return [(NEXT_EPISODE, "Play next episode")]

    def _video_actions(self):
        """A movie or episode gets Resume and Play from beginning, or just Play."""
        resume_ticks = (self._item.get("UserData") or {}).get("PlaybackPositionTicks") or 0
        actions = []
        if resume_ticks:
            actions.append((RESUME, f"Resume from {format_time(resume_ticks / TICKS_PER_SECOND)}"))
            actions.append((PLAY, "Play from beginning"))
        else:
            actions.append((PLAY, "Play"))
        return actions

    def _show_seasons(self):
        """Shows get a row of seasons. Other items leave it empty, which hides it."""
        seasons = []
        if self._item.get("Type") == "Series":
            try:
                seasons = self.client.get_seasons(self.item_id)
            except JellyfinError as error:
                log(f"Couldn't load seasons of {self.item_id}: {error}", xbmc.LOGWARNING)

        self._seasons = {season["Id"]: season for season in seasons}
        row = self.getControl(SEASONS_ROW)
        row.reset()
        row.addItems([season_item(self.client, season) for season in seasons])

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

        if action == NEXT_EPISODE:
            play(self.client, self._next_episode)
        elif action == RESUME:
            ticks = (self._item.get("UserData") or {}).get("PlaybackPositionTicks") or 0
            play(self.client, self._item, start_seconds=ticks / TICKS_PER_SECOND)
        else:
            play(self.client, self._item, start_seconds=0)
        self._refresh_after_playback()

    def _open_selected_season(self):
        # Imported here because the episodes screen opens detail pages itself.
        from resources.lib.episodes import show_episodes

        selected = self.getControl(SEASONS_ROW).getSelectedItem()
        if selected is None:
            return
        show_episodes(self.client, self._item, selected.getProperty("id"))

        # Watching episodes changes the next episode and the unwatched counts.
        position = self.getControl(SEASONS_ROW).getSelectedPosition()
        self._show_actions()
        self._show_seasons()
        row = self.getControl(SEASONS_ROW)
        if row.size():
            row.selectItem(min(position, row.size() - 1))
            self.setFocusId(SEASONS_ROW)

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

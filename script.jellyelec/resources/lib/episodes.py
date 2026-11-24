"""The episodes screen: a season bar along the top and that season's episodes below."""

import xbmc
import xbmcgui

from resources.lib.api import JellyfinError
from resources.lib.detail import show_details
from resources.lib.formatting import meta_line
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import backdrop_url, episode_item, episode_thumb_url

# Control IDs, matching jellyelec-episodes.xml.
SEASON_BAR = 600
EPISODE_LIST = 610

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def show_episodes(client, series, season_id):
    """Open the episodes screen for a show, starting on one season. Returns when the user goes back."""
    window = EpisodesWindow("jellyelec-episodes.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.series = series
    window.season_id = season_id
    window.doModal()
    del window


class EpisodesWindow(xbmcgui.WindowXML):
    """Set client, series (Jellyfin data) and season_id before calling doModal()."""

    client = None
    series = None
    season_id = None

    _loaded = False
    _shown_season_id = None
    _episodes = None  # Jellyfin data for the listed episodes, keyed by item ID

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        # onInit runs again after the detail page closes; load only once.
        if self._loaded:
            return
        self._loaded = True
        self.setProperty("series_name", self.series.get("Name", ""))
        self.setProperty("backdrop", backdrop_url(self.client, self.series) or "")
        self._load_seasons()

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()
            return
        focus = self.getFocusId()
        if focus == SEASON_BAR:
            self._show_selected_season()
        elif focus == EPISODE_LIST:
            self._update_episode_panel()

    def onClick(self, control_id):
        if control_id == EPISODE_LIST:
            self._open_selected_episode()

    # Seasons ----------------------------------------------------------------------

    def _load_seasons(self):
        try:
            seasons = self.client.get_seasons(self.series["Id"])
        except JellyfinError as error:
            log(f"Couldn't load seasons of {self.series['Id']}: {error}", xbmc.LOGWARNING)
            _notify("Couldn't load the seasons.")
            return

        bar = self.getControl(SEASON_BAR)
        bar.reset()
        for position, season in enumerate(seasons):
            entry = xbmcgui.ListItem(label=season.get("Name", ""), offscreen=True)
            entry.setProperty("id", season["Id"])
            bar.addItem(entry)
            if season["Id"] == self.season_id:
                bar.selectItem(position)

        self._show_selected_season()
        self.setFocusId(EPISODE_LIST if self.getControl(EPISODE_LIST).size() else SEASON_BAR)

    def _show_selected_season(self, force=False):
        """Load the selected season's episodes, unless they're already showing."""
        selected = self.getControl(SEASON_BAR).getSelectedItem()
        if selected is None:
            return
        season_id = selected.getProperty("id")
        if season_id == self._shown_season_id and not force:
            return
        self._shown_season_id = season_id

        try:
            episodes = self.client.get_episodes(self.series["Id"], season_id)
        except JellyfinError as error:
            log(f"Couldn't load episodes of season {season_id}: {error}", xbmc.LOGWARNING)
            _notify("Couldn't load the episodes.")
            episodes = []

        self._episodes = {episode["Id"]: episode for episode in episodes}
        episode_list = self.getControl(EPISODE_LIST)
        episode_list.reset()
        episode_list.addItems([episode_item(self.client, episode) for episode in episodes])
        self._update_episode_panel()

    # Episodes ---------------------------------------------------------------------

    def _update_episode_panel(self):
        """Show the focused episode's picture and details on the right."""
        selected = self.getControl(EPISODE_LIST).getSelectedItem()
        data = self._episodes.get(selected.getProperty("id")) if selected else None
        data = data or {}
        self.setProperty("episode_title", selected.getLabel() if selected else "")
        self.setProperty("episode_meta", meta_line(data))
        self.setProperty("episode_plot", data.get("Overview", ""))
        self.setProperty("episode_thumb", (episode_thumb_url(self.client, data) if data else None) or "")

    def _open_selected_episode(self):
        episode_list = self.getControl(EPISODE_LIST)
        selected = episode_list.getSelectedItem()
        if selected is None:
            return
        position = episode_list.getSelectedPosition()

        show_details(self.client, selected.getProperty("id"))

        # Reload so watched marks are current, then return to the same episode.
        self._show_selected_season(force=True)
        if episode_list.size():
            episode_list.selectItem(min(position, episode_list.size() - 1))
            self.setFocusId(EPISODE_LIST)
            self._update_episode_panel()


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

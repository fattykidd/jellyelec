"""The home screen: library bar, spotlight and poster rows."""

import xbmc
import xbmcgui

from resources.lib import storage
from resources.lib.api import JellyfinError
from resources.lib.kodi import ADDON_NAME, ADDON_VERSION, log
from resources.lib.listitems import library_item, media_item
from resources.lib.playback import play

# Control IDs, matching jellyelec-home.xml.
LIBRARY_BAR = 100
CONTINUE_WATCHING_ROW = 200

SUPPORTED_LIBRARY_TYPES = {"movies", "tvshows"}
CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


class HomeWindow(xbmcgui.WindowXML):
    """Set client and connection before calling doModal()."""

    client = None
    connection = None
    signed_out = False

    _loaded = False
    _library_id = None
    _row_items = None  # Jellyfin data for the row's posters, keyed by item ID

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        self.setProperty("version", ADDON_VERSION)
        self.setProperty("user_name", self.connection.user_name)

        # onInit runs again whenever a dialog closes over this window; load only once.
        if not self._loaded:
            self._loaded = True
            self._load_libraries()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in CLOSE_ACTIONS:
            self.close()
        elif action_id == xbmcgui.ACTION_CONTEXT_MENU:
            self._confirm_sign_out()
        elif self.getFocusId() == LIBRARY_BAR:
            self._show_selected_library()

    def onClick(self, control_id):
        if control_id == CONTINUE_WATCHING_ROW:
            self._play_selected()

    # Libraries ------------------------------------------------------------------

    def _load_libraries(self):
        try:
            libraries = [
                library
                for library in self.client.get_libraries()
                if library.get("CollectionType") in SUPPORTED_LIBRARY_TYPES
            ]
        except JellyfinError as error:
            log(f"Couldn't load libraries: {error}", xbmc.LOGWARNING)
            self._notify("Couldn't load your libraries.")
            return

        bar = self.getControl(LIBRARY_BAR)
        bar.reset()
        bar.addItems([library_item(library) for library in libraries])

        if libraries:
            self._show_selected_library()
            self.setFocusId(LIBRARY_BAR)

    def _show_selected_library(self):
        """Reload the rows when the selected library changes."""
        selected = self.getControl(LIBRARY_BAR).getSelectedItem()
        if selected is None:
            return
        library_id = selected.getProperty("id")
        if library_id == self._library_id:
            return
        self._library_id = library_id

        try:
            items = self.client.get_resume_items(library_id)
        except JellyfinError as error:
            log(f"Couldn't load Continue Watching for {selected.getLabel()}: {error}", xbmc.LOGWARNING)
            self._notify("Couldn't load Continue Watching.")
            items = []

        self._row_items = {item["Id"]: item for item in items}
        row = self.getControl(CONTINUE_WATCHING_ROW)
        row.reset()
        row.addItems([media_item(self.client, item) for item in items])

    # Playback -------------------------------------------------------------------

    def _play_selected(self):
        selected = self.getControl(CONTINUE_WATCHING_ROW).getSelectedItem()
        if selected is None:
            return
        data = self._row_items.get(selected.getProperty("id"))
        if data is None:
            return

        play(self.client, data)
        self._refresh_rows()

    def _refresh_rows(self):
        """Reload the rows so positions and watched items are up to date."""
        self._library_id = None
        self._show_selected_library()
        if self.getControl(CONTINUE_WATCHING_ROW).size():
            self.setFocusId(CONTINUE_WATCHING_ROW)
        else:
            self.setFocusId(LIBRARY_BAR)

    # Helpers --------------------------------------------------------------------

    def _confirm_sign_out(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, f"Sign out of {self.connection.server_name}?"):
            self.connection.sign_out()
            storage.save(self.connection)
            self.signed_out = True
            self.close()

    @staticmethod
    def _notify(message):
        xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

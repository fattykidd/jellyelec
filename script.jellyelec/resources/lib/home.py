"""The home screen: library bar, spotlight and stacked poster rows."""

import xbmc
import xbmcgui

from resources.lib import appliance, storage
from resources.lib.api import JellyfinError
from resources.lib.detail import show_details
from resources.lib.formatting import episode_line, meta_line
from resources.lib.kodi import ADDON_NAME, ADDON_VERSION, log
from resources.lib.library import show_library
from resources.lib.live_tv import show_live_tv
from resources.lib.listitems import backdrop_url, library_item, media_item
from resources.lib.settings_screen import SIGN_OUT, show_settings

# Control IDs, matching jellyelec-home.xml.
LIBRARY_BAR = 100
CONTINUE_WATCHING_ROW = 200
NEXT_UP_ROW = 205
RECENTLY_ADDED_ROW = 210
RANDOM_ROW = 220
ROWS = (CONTINUE_WATCHING_ROW, NEXT_UP_ROW, RECENTLY_ADDED_ROW, RANDOM_ROW)

# The item type each library holds, as Jellyfin names it.
LIBRARY_ITEM_TYPES = {"movies": "Movie", "tvshows": "Series"}
LIVE_TV = "livetv"

# The Settings tile at the end of the library bar. Not a Jellyfin library, so it gets a
# collection type of its own.
SETTINGS = "jellyelec_settings"
SETTINGS_TILE = {"Id": SETTINGS, "Name": "Settings", "CollectionType": SETTINGS}

# Messages shown in place of the rows for tiles that open their own screen.
TILE_MESSAGES = {LIVE_TV: "Press OK to open Live TV.", SETTINGS: "Press OK to open Settings."}
CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


class HomeWindow(xbmcgui.WindowXML):
    """Set client and connection before calling doModal().

    When it closes, next_step says what app.py should do: settings_screen.SIGN_OUT,
    RUN_SETUP or EXIT_TO_KODI, or None to leave JellyELEC.
    """

    client = None
    connection = None
    next_step = None

    _loaded = False
    _library_id = None
    _row_data = None  # {row ID: {item ID: Jellyfin data}}

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        self.setProperty("version", ADDON_VERSION)
        self.setProperty("user_name", self.connection.user_name)

        # onInit runs again whenever a dialog closes over this window; load only once.
        if not self._loaded:
            self._loaded = True
            self._row_data = {row: {} for row in ROWS}
            self._load_libraries()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in CLOSE_ACTIONS:
            self._go_back()
            return
        if action_id == xbmcgui.ACTION_CONTEXT_MENU:
            self._confirm_sign_out()
            return

        focus = self.getFocusId()
        if focus == LIBRARY_BAR:
            self._show_selected_library()
        elif focus in ROWS:
            self._update_spotlight(focus)

    def onClick(self, control_id):
        if control_id == LIBRARY_BAR:
            self._open_selected_library()
        elif control_id in ROWS:
            self._open_selected_item(control_id)

    # Libraries ------------------------------------------------------------------

    def _load_libraries(self):
        try:
            libraries = [
                library
                for library in self.client.get_libraries()
                if library.get("CollectionType") in LIBRARY_ITEM_TYPES
                or library.get("CollectionType") == LIVE_TV
            ]
        except JellyfinError as error:
            log(f"Couldn't load libraries: {error}", xbmc.LOGWARNING)
            self._notify("Couldn't load your libraries.")
            libraries = []

        # Settings is always there, so the box can be sorted out even if the server isn't.
        bar = self.getControl(LIBRARY_BAR)
        bar.reset()
        bar.addItems([library_item(library) for library in libraries + [SETTINGS_TILE]])
        self._show_selected_library()
        self.setFocusId(LIBRARY_BAR)

    def _selected_library(self):
        return self.getControl(LIBRARY_BAR).getSelectedItem()

    def _show_selected_library(self):
        """Load the rows when the selected library changes."""
        self._show_library(self._selected_library())

    def _show_library(self, library):
        """Load the rows for a library tile, unless they're already showing."""
        if library is None or library.getProperty("id") == self._library_id:
            return
        self._library_id = library.getProperty("id")
        self._load_rows(library)
        self._update_spotlight()

    def _load_rows(self, library, keep_random=False):
        """Fill the rows for a library. keep_random leaves the Random row as it is."""
        library_id = library.getProperty("id")
        collection_type = library.getProperty("collection_type")
        if collection_type in TILE_MESSAGES:
            # Live TV and Settings have their own screens; their home page says how to open them.
            for row in ROWS:
                self._fill_row(row, lambda: [])
            self.setProperty("empty_message", TILE_MESSAGES[collection_type])
            return

        self.setProperty("empty_message", "Nothing to show in this library yet.")
        item_type = LIBRARY_ITEM_TYPES[collection_type]
        is_tv = item_type == "Series"

        self._fill_row(CONTINUE_WATCHING_ROW, lambda: self.client.get_resume_items(library_id))
        self._fill_row(NEXT_UP_ROW, lambda: self.client.get_next_up_items(library_id) if is_tv else [])
        self._fill_row(RECENTLY_ADDED_ROW, lambda: self.client.get_latest_items(library_id))
        if not keep_random:
            self._fill_row(RANDOM_ROW, lambda: self.client.get_random_items(library_id, item_type))

    def _fill_row(self, row_id, fetch):
        try:
            items = fetch()
        except JellyfinError as error:
            log(f"Couldn't load row {row_id}: {error}", xbmc.LOGWARNING)
            items = []

        self._row_data[row_id] = {item["Id"]: item for item in items}
        row = self.getControl(row_id)
        row.reset()
        row.addItems([media_item(self.client, item) for item in items])

    def _open_selected_library(self):
        selected = self._selected_library()
        if selected is None:
            return
        collection_type = selected.getProperty("collection_type")
        if collection_type == LIVE_TV:
            show_live_tv(self.client)
            return
        if collection_type == SETTINGS:
            self._open_settings()
            return
        item_type = LIBRARY_ITEM_TYPES[collection_type]
        show_library(self.client, selected.getProperty("id"), selected.getLabel(), item_type)
        self._refresh_rows()

    # Spotlight --------------------------------------------------------------------

    def _update_spotlight(self, row_id=None, position=None):
        """Show the focused poster's details. With no row given, use the first row with items.

        position names the poster outright, for just after selectItem(), which Kodi applies
        a moment later.
        """
        rows = (row_id,) if row_id else ROWS
        data = None
        for row in rows:
            control = self.getControl(row)
            selected = control.getListItem(position) if position is not None else control.getSelectedItem()
            if selected is not None:
                data = self._row_data[row].get(selected.getProperty("id"))
                break

        data = data or {}
        is_episode = data.get("Type") == "Episode"
        details = [part for part in (episode_line(data), meta_line(data)) if part]
        self.setProperty("spot_show_title", data.get("SeriesName", "") if is_episode else "")
        self.setProperty("spot_title", data.get("Name", ""))
        self.setProperty("spot_meta", "     ".join(details))
        self.setProperty("spot_plot", data.get("Overview", ""))
        self.setProperty("spot_backdrop", (backdrop_url(self.client, data) if data else None) or "")

    # Details --------------------------------------------------------------------

    def _open_selected_item(self, row_id):
        selected = self.getControl(row_id).getSelectedItem()
        if selected is None:
            return
        item_id = selected.getProperty("id")
        position = self.getControl(row_id).getSelectedPosition()
        show_details(self.client, item_id)
        self._refresh_rows(focus_row=row_id, item_id=item_id, position=position)

    def _refresh_rows(self, focus_row=None, item_id=None, position=0):
        """Reload the rows so progress and watched items are up to date, keeping the place.

        With focus_row, focus returns to item_id in that row; if it has gone from the row
        (finished, so no longer in Continue Watching), to the poster now in its old position.
        The Random row isn't reshuffled, so what was just opened is still there.
        """
        library = self._selected_library()
        if library is not None:
            self._load_rows(library, keep_random=True)

        row = self.getControl(focus_row) if focus_row else None
        if row is None or not row.size():
            self.setFocusId(LIBRARY_BAR)
            self._update_spotlight()
            return

        ids = [row.getListItem(index).getProperty("id") for index in range(row.size())]
        index = ids.index(item_id) if item_id in ids else min(position, row.size() - 1)
        row.selectItem(index)
        self.setFocusId(focus_row)
        self._update_spotlight(focus_row, index)

    # Back --------------------------------------------------------------------------

    def _go_back(self):
        """Step back one stage: to the start of a row, up to the library bar, then to the first library.

        Only after that does Back leave JellyELEC, and never in appliance mode, where there's
        nothing behind it (Settings has Exit to Kodi for that).
        """
        focus = self.getFocusId()
        if focus in ROWS:
            row = self.getControl(focus)
            if row.getSelectedPosition() > 0:
                row.selectItem(0)
                self._update_spotlight(focus, 0)
            else:
                self.setFocusId(LIBRARY_BAR)
            return

        bar = self.getControl(LIBRARY_BAR)
        if focus == LIBRARY_BAR and bar.getSelectedPosition() > 0:
            bar.selectItem(0)
            self._show_library(bar.getListItem(0))
            return

        if not appliance.is_enabled():
            self.close()

    # Settings and signing out ----------------------------------------------------

    def _open_settings(self):
        next_step = show_settings(self.connection)
        if next_step == SIGN_OUT:
            self._sign_out()
        elif next_step:
            self.next_step = next_step
            self.close()

    def _confirm_sign_out(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, f"Sign out of {self.connection.server_name}?"):
            self._sign_out()

    def _sign_out(self):
        self.connection.sign_out()
        storage.save(self.connection)
        self.next_step = SIGN_OUT
        self.close()

    # Helpers --------------------------------------------------------------------

    @staticmethod
    def _notify(message):
        xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

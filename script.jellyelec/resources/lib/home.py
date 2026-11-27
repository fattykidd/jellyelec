"""The home screen: library bar, spotlight and stacked poster rows."""

from datetime import datetime, timezone

import xbmc
import xbmcgui

from resources.lib import appliance, storage
from resources.lib.api import JellyfinError
from resources.lib.detail import show_details
from resources.lib.formatting import ends_at_text, episode_line, spotlight_meta
from resources.lib.kodi import ADDON_NAME, log
from resources.lib.library import show_library
from resources.lib.live_tv import show_live_tv
from resources.lib.library_bar import LibraryBar
from resources.lib.listitems import backdrop_url, logo_url, media_item
from resources.lib.settings_screen import SIGN_OUT, show_settings

# Control IDs, matching jellyelec-home.xml. The library bar's are in library_bar.py.
SETTINGS_BUTTON = 110
CONTINUE_WATCHING_ROW = 200
NEXT_UP_ROW = 205
RECENTLY_ADDED_ROW = 210
RANDOM_ROW = 220
ROWS = (CONTINUE_WATCHING_ROW, NEXT_UP_ROW, RECENTLY_ADDED_ROW, RANDOM_ROW)

# The item type each library holds, as Jellyfin names it.
LIBRARY_ITEM_TYPES = {"movies": "Movie", "tvshows": "Series"}
LIVE_TV = "livetv"

# Messages shown in place of the rows for tiles that open their own screen.
TILE_MESSAGES = {LIVE_TV: "Press OK to open Live TV."}
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
        # onInit runs again whenever a dialog closes over this window; load only once.
        if not self._loaded:
            self._loaded = True
            self._row_data = {row: {} for row in ROWS}
            self._bar = LibraryBar(self)
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
        if self._bar.follow_focus(focus):
            self._show_selected_library()
        elif focus in ROWS:
            self._update_spotlight(focus)

    def onClick(self, control_id):
        if control_id == SETTINGS_BUTTON:
            self._open_settings()
        elif self._bar.owns(control_id):
            self._bar.follow_focus(control_id)
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

        self._bar.fill(libraries)
        self._show_selected_library()
        # With no libraries, Settings is the way to sort the box out.
        if libraries:
            self._bar.focus()
        else:
            self.setFocusId(SETTINGS_BUTTON)

    def _selected_library(self):
        """The selected library's data from Jellyfin, or None."""
        return self._bar.selected

    def _show_selected_library(self):
        """Load the rows when the selected library changes."""
        self._show_library(self._selected_library())

    def _show_library(self, library):
        """Load the rows for a library tile, unless they're already showing."""
        if library is None or library["Id"] == self._library_id:
            return
        self._library_id = library["Id"]
        self._load_rows(library)
        self._update_spotlight()

    def _load_rows(self, library, keep_random=False):
        """Fill the rows for a library. keep_random leaves the Random row as it is."""
        library_id = library["Id"]
        collection_type = library.get("CollectionType", "")
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
        collection_type = selected.get("CollectionType", "")
        if collection_type == LIVE_TV:
            show_live_tv(self.client)
            return
        item_type = LIBRARY_ITEM_TYPES[collection_type]
        show_library(self.client, selected["Id"], selected.get("Name", ""), item_type)
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
        title = data.get("SeriesName", "") if is_episode else data.get("Name", "")
        episode = (episode_line(data), data.get("Name", "")) if is_episode else ()
        details = (spotlight_meta(data), ends_at_text(data, datetime.now(timezone.utc)))
        self.setProperty("spot_title", title.upper())
        self.setProperty("spot_logo", (logo_url(self.client, data) if data else None) or "")
        self.setProperty("spot_episode", "  ·  ".join(part for part in episode if part))
        self.setProperty("spot_meta", "  ·  ".join(part for part in details if part))
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
            self._bar.focus()
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
        if focus == SETTINGS_BUTTON:
            self._bar.focus()
            return
        if focus in ROWS:
            row = self.getControl(focus)
            if row.getSelectedPosition() > 0:
                row.selectItem(0)
                self._update_spotlight(focus, 0)
            else:
                self._leave_rows_for_library_bar()
            return

        if self._bar.owns(focus) and self._bar.selected_index > 0:
            self._bar.select(0)
            self._bar.focus()
            self._show_selected_library()
            return

        if not appliance.is_enabled():
            self.close()

    def _leave_rows_for_library_bar(self):
        """Go up to the library bar, so that Down comes back to the first row, not this one.

        The stack of rows remembers its last focused row; focusing the first row on the way
        up makes that the one it remembers.
        """
        first_row = next((row for row in ROWS if self.getControl(row).size()), None)
        if first_row is not None:
            self.setFocusId(first_row)
        self._bar.focus()
        self._update_spotlight()

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

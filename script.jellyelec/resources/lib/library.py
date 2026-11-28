"""The library grid: every movie or show in one library, A to Z.

The same screen shows a collection's movies, in release order, when a collection is opened.
"""

import threading
from datetime import datetime, timedelta

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import versions
from resources.lib.api import JellyfinError
from resources.lib.detail import show_details
from resources.lib.formatting import clock_text, media_summary
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import media_item

# Control IDs, matching jellyelec-library.xml.
POSTER_GRID = 500

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# The focused title's resolution and audio come from a request of their own, made once focus
# has rested on it this long, so scrolling past posters doesn't send a request for each.
MEDIA_DETAILS_DELAY_SECONDS = 0.4

# Add-on setting: show each movie collection once in the grid, in place of its movies.
GROUP_COLLECTIONS_SETTING = "group_collections"

# Jellyfin's item types for movies and collections.
MOVIE = "Movie"
COLLECTION = "BoxSet"


def show_library(client, library_id, library_name, item_type):
    """Open the grid for one library. Returns when the user goes back."""
    _show_grid(client, library_id, library_name, item_type)


def show_collection(client, collection_id, collection_name):
    """Open the grid for one collection's movies. Returns when the user goes back."""
    _show_grid(client, collection_id, collection_name, COLLECTION)


def _show_grid(client, parent_id, title, item_type):
    window = LibraryWindow("jellyelec-library.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.library_id = parent_id
    window.library_name = title
    window.item_type = item_type
    window.doModal()
    del window


class LibraryWindow(xbmcgui.WindowXML):
    """Set client, library_id, library_name and item_type before calling doModal().

    For a collection, library_id is the collection's ID and item_type is COLLECTION.
    """

    client = None
    library_id = None
    library_name = ""
    item_type = None

    _loaded = False
    _media_timer = None

    def onInit(self):
        # onInit runs again after the detail page closes; load only once.
        if self._loaded:
            return
        self._loaded = True
        self._media_summaries = {}  # item ID -> "4K · Dolby Vision · Dolby TrueHD Atmos 7.1"
        self._media_timer = None
        self.setProperty("library_name", self.library_name)
        self._load()

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            # Back goes to the top of the grid first, then out.
            grid = self.getControl(POSTER_GRID)
            if grid.getSelectedPosition() > 0:
                grid.selectItem(0)
                self._show_focused_details(grid.getListItem(0))
            else:
                self._cancel_media_request()
                self.close()
            return
        self._show_focused_details()

    def onClick(self, control_id):
        if control_id != POSTER_GRID:
            return
        selected = self.getControl(POSTER_GRID).getSelectedItem()
        if selected is None:
            return
        if selected.getProperty("type") == COLLECTION:
            show_collection(self.client, selected.getProperty("id"), selected.getLabel())
        else:
            show_details(self.client, selected.getProperty("id"))

    def _load(self):
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            items = self._fetch_items()
        except JellyfinError as error:
            log(f"Couldn't load library {self.library_name}: {error}", xbmc.LOGWARNING)
            xbmcgui.Dialog().notification(
                ADDON_NAME, f"Couldn't load {self.library_name}.", xbmcgui.NOTIFICATION_WARNING
            )
            items = []
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

        collections = sum(1 for item in items if item.get("Type") == COLLECTION)
        log(f"{self.library_name}: {len(items)} items, {collections} of them collections.")

        grid = self.getControl(POSTER_GRID)
        grid.reset()
        grid.addItems([media_item(self.client, item) for item in items])
        self.setProperty("item_count", str(len(items)))
        if items:
            self.setFocusId(POSTER_GRID)
            self._show_focused_details(grid.getListItem(0))

    def _fetch_items(self):
        if self.item_type == COLLECTION:
            return self.client.get_collection_items(self.library_id)
        group = self.item_type == MOVIE and xbmcaddon.Addon().getSettingBool(GROUP_COLLECTIONS_SETTING)
        return self.client.get_library_items(self.library_id, self.item_type, group_collections=group)

    # The focused title's details ---------------------------------------------------

    def _show_focused_details(self, item=None):
        """Ends at, now, and the resolution and audio once focus rests (from the server)."""
        item = item or self.getControl(POSTER_GRID).getSelectedItem()
        if item is None:
            return
        remaining = item.getProperty("remaining_seconds")
        ends = ""
        if remaining and int(remaining) > 0:
            ends = f"Ends at {clock_text(datetime.now().astimezone() + timedelta(seconds=int(remaining)))}"
        self.setProperty("focused_ends", ends)

        item_id = item.getProperty("id")
        if not remaining:  # a show or collection: no single file to describe
            self.setProperty("focused_media", "")
            return
        if item_id in self._media_summaries:
            self.setProperty("focused_media", self._media_summaries[item_id])
            return
        self.setProperty("focused_media", "")
        self._cancel_media_request()
        self._media_timer = threading.Timer(MEDIA_DETAILS_DELAY_SECONDS, self._fetch_media_summary, (item_id,))
        self._media_timer.daemon = True
        self._media_timer.start()

    def _fetch_media_summary(self, item_id):
        try:
            data = self.client.get_item(item_id)
        except JellyfinError as error:
            log(f"Couldn't get the media details of {item_id}: {error}", xbmc.LOGWARNING)
            return
        summary = media_summary(data, versions.chosen_source(data))
        self._media_summaries[item_id] = summary
        selected = self.getControl(POSTER_GRID).getSelectedItem()
        if selected is not None and selected.getProperty("id") == item_id:
            self.setProperty("focused_media", summary)

    def _cancel_media_request(self):
        if self._media_timer is not None:
            self._media_timer.cancel()
            self._media_timer = None

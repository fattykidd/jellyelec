"""The library grid: every movie or show in one library, A to Z.

The same screen shows a collection's movies, in release order, when a collection is opened.
"""

import threading
from datetime import datetime, timedelta

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib.api import JellyfinError
from resources.lib.detail import show_details
from resources.lib.formatting import clock_text
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import backdrop_url, media_item, poster_url
from resources.lib.media_details import MediaSummaryLoader

# Control IDs, matching jellyelec-library.xml.
POSTER_GRID = 500

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

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
    _media = None
    _closing = False

    def onInit(self):
        # onInit runs again after the detail page closes; load only once.
        if self._loaded:
            return
        self._loaded = True
        self._media = MediaSummaryLoader(self.client, self._show_media_summary)
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
                self._closing = True
                self._media.cancel()
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
            self._fill_in_collection_artwork(items)

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

        if not remaining:  # a show or collection: no single file to describe
            self.setProperty("focused_media", "")
            self._media.cancel()
            return
        self.setProperty("focused_media", self._media.request(item.getProperty("id")) or "")

    def _show_media_summary(self, item_id, summary):
        selected = self.getControl(POSTER_GRID).getSelectedItem()
        if selected is not None and selected.getProperty("id") == item_id:
            self.setProperty("focused_media", summary)

    # Collection artwork -------------------------------------------------------------

    def _fill_in_collection_artwork(self, items):
        """Collections without artwork of their own borrow their first movie's poster and
        backdrop. Done in the background, as it takes a request per collection."""
        bare = [
            (index, item) for index, item in enumerate(items)
            if item.get("Type") == COLLECTION and not item.get("ImageTags", {}).get("Primary")
        ]
        if bare:
            log(f"{len(bare)} collections have no poster; borrowing their first movie's.")
            threading.Thread(target=self._borrow_artwork, args=(bare,), daemon=True).start()

    def _borrow_artwork(self, bare):
        grid = self.getControl(POSTER_GRID)
        for index, collection in bare:
            if self._closing:
                return
            try:
                movies = self.client.get_collection_items(collection["Id"])
            except JellyfinError as error:
                log(f"Couldn't look inside collection {collection.get('Name')}: {error}", xbmc.LOGWARNING)
                continue
            first = next((movie for movie in movies if poster_url(self.client, movie)), None)
            if first is None:
                continue
            art = {"poster": poster_url(self.client, first)}
            if not collection.get("BackdropImageTags"):
                art["fanart"] = backdrop_url(self.client, first)
            list_item = grid.getListItem(index)
            if list_item.getProperty("id") == collection["Id"]:
                list_item.setArt({kind: url for kind, url in art.items() if url})
                # The poster is a movie's, so the tile shows the collection's name over it.
                list_item.setProperty("borrowed_poster", "true")

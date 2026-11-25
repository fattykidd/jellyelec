"""The chapter list, shown over the picture when Back is pressed during a movie or episode.

Picking a chapter jumps to it; Stop ends playback; Back closes the list and the video
carries on. Chapter names, times and pictures come from Jellyfin.
"""

import xbmcgui

from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import format_time
from resources.lib.kodi import ADDON_PATH, log

# Control IDs, matching jellyelec-chapters.xml.
CHAPTER_LIST = 1100
STOP_BUTTON = 1110

# Returned when the user chooses Stop.
STOP = "stop"

CHAPTER_IMAGE_WIDTH = 480
CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def choose_chapter(client, data, position_seconds):
    """Show the chapter list. Returns a chapter's start in seconds, STOP, or None to carry on."""
    window = ChapterWindow("jellyelec-chapters.xml", ADDON_PATH, "Default", "1080i")
    chapters = _chapters(client, data)
    window.items = [_chapter_item(client, data, index, chapter) for index, chapter in enumerate(chapters)]
    window.current = _current_chapter(window.items, position_seconds)
    window.title = data.get("Name", "")
    window.doModal()
    choice = window.choice
    del window
    return choice


class ChapterWindow(xbmcgui.WindowXMLDialog):
    """Set items, current and title before calling doModal(). The answer is left in choice."""

    items = ()
    current = 0
    title = ""
    choice = None

    def onInit(self):
        self.setProperty("title", self.title)
        chapter_list = self.getControl(CHAPTER_LIST)
        chapter_list.reset()
        chapter_list.addItems(self.items)
        if self.items:
            chapter_list.selectItem(self.current)
            self.setFocusId(CHAPTER_LIST)
        else:
            self.setProperty("no_chapters", "true")
            self.setFocusId(STOP_BUTTON)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()

    def onClick(self, control_id):
        if control_id == STOP_BUTTON:
            self.choice = STOP
        elif control_id == CHAPTER_LIST:
            self.choice = float(self.getControl(CHAPTER_LIST).getSelectedItem().getProperty("start"))
        else:
            return
        self.close()


# Helpers ----------------------------------------------------------------------------

def _chapters(client, data):
    """The item's chapters. Fetched if the details we were given don't include them."""
    if "Chapters" in data:
        return data["Chapters"] or []
    try:
        return client.get_item(data["Id"]).get("Chapters") or []
    except JellyfinError as error:
        log(f"Couldn't get chapters for {data['Id']}: {error}")
        return []


def _chapter_item(client, data, index, chapter):
    start = (chapter.get("StartPositionTicks") or 0) / TICKS_PER_SECOND
    name = chapter.get("Name") or f"Chapter {index + 1}"
    item = xbmcgui.ListItem(label=name, label2=format_time(start), offscreen=True)
    item.setProperty("start", str(start))
    tag = chapter.get("ImageTag")
    if tag:
        item.setArt({"thumb": client.image_url(data["Id"], f"Chapter/{index}", tag, max_width=CHAPTER_IMAGE_WIDTH)})
    return item


def _current_chapter(items, position_seconds):
    """The index of the chapter that's playing: the last one starting at or before now."""
    current = 0
    for index, item in enumerate(items):
        if float(item.getProperty("start")) <= position_seconds:
            current = index
    return current

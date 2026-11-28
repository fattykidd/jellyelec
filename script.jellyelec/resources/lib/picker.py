"""A list to pick one thing from, in JellyELEC's look: used in place of Kodi's own select
dialog, such as for audio tracks and subtitles during playback.
"""

import xbmcgui

from resources.lib.kodi import ADDON_PATH

# Control IDs, matching jellyelec-picker.xml.
OPTION_LIST = 1400

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def choose(title, options, current=-1):
    """Show options (a list of (label, second line) pairs, the second line may be "") and
    return the index picked, or None if Back was pressed. current is marked and focused."""
    window = PickerWindow("jellyelec-picker.xml", ADDON_PATH, "Default", "1080i")
    window.title = title
    window.options = options
    window.current = current
    window.doModal()
    choice = window.choice
    del window
    return choice


class PickerWindow(xbmcgui.WindowXMLDialog):
    """Set title, options and current before calling doModal(). The answer is left in choice."""

    title = ""
    options = ()
    current = -1
    choice = None

    def onInit(self):
        self.setProperty("title", self.title)
        option_list = self.getControl(OPTION_LIST)
        option_list.reset()
        for index, (label, detail) in enumerate(self.options):
            item = xbmcgui.ListItem(label=label, offscreen=True)
            item.setProperty("detail", detail or "")
            item.setProperty("current", "true" if index == self.current else "")
            option_list.addItem(item)
        if 0 <= self.current < len(self.options):
            option_list.selectItem(self.current)
        self.setFocusId(OPTION_LIST)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()

    def onClick(self, control_id):
        if control_id == OPTION_LIST:
            self.choice = self.getControl(OPTION_LIST).getSelectedPosition()
            self.close()

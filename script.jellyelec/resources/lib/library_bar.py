"""The library bar along the top of the home screen.

Kodi's lists give every item the same width, so long library names were cut short. The bar is
instead a horizontal grouplist of buttons (IDs 1001-1012 in jellyelec-home.xml) that each size
themselves to their name; the grouplist slides along to keep the focused one in view. This
class fills the buttons, hides the spare ones, and tracks which library is selected.

The selected library is the one whose rows are showing. While the bar has focus, the focused
button is the selected one (a blue pill); when focus moves down to the rows, the selected
library keeps a blue underline and white text.
"""

from resources.lib.kodi import log

GROUP_ID = 100
FIRST_BUTTON_ID = 1001
MAX_LIBRARIES = 12

SELECTED_COLOR = "FFF2F2F5"
UNSELECTED_COLOR = "FFB7B9C6"
FOCUSED_COLOR = "FFFFFFFF"
UNDERLINE_COLOR = "FF00A4DC"  # Jellyfin blue
NO_UNDERLINE = "00FFFFFF"


class LibraryBar:
    def __init__(self, window):
        self._window = window
        self._libraries = []
        self._selected = 0

    @property
    def libraries(self):
        return self._libraries

    @property
    def selected(self):
        """The selected library's data from Jellyfin, or None if there are no libraries."""
        return self._libraries[self._selected] if self._libraries else None

    @property
    def selected_index(self):
        return self._selected

    def fill(self, libraries):
        if len(libraries) > MAX_LIBRARIES:
            log(f"{len(libraries)} libraries; the bar shows the first {MAX_LIBRARIES}.")
        self._libraries = libraries[:MAX_LIBRARIES]
        self._selected = 0
        for index in range(MAX_LIBRARIES):
            self._button(index).setVisible(index < len(self._libraries))
        self._paint()

    def owns(self, control_id):
        """True if control_id is one of the bar's buttons in use."""
        return FIRST_BUTTON_ID <= control_id < FIRST_BUTTON_ID + len(self._libraries)

    def follow_focus(self, control_id):
        """Make the focused button the selected library. Returns True if the selection changed."""
        if not self.owns(control_id):
            return False
        index = control_id - FIRST_BUTTON_ID
        if index == self._selected:
            return False
        self.select(index)
        return True

    def select(self, index):
        self._selected = index
        self._paint()

    def focus(self):
        """Put focus on the selected library's button."""
        if self._libraries:
            self._window.setFocusId(FIRST_BUTTON_ID + self._selected)

    def _paint(self):
        for index, library in enumerate(self._libraries):
            is_selected = index == self._selected
            self._button(index).setLabel(
                library.get("Name", ""),
                textColor=SELECTED_COLOR if is_selected else UNSELECTED_COLOR,
                focusedColor=FOCUSED_COLOR,
            )
            self._window.setProperty(
                f"library_underline_{FIRST_BUTTON_ID + index}",
                UNDERLINE_COLOR if is_selected else NO_UNDERLINE,
            )

    def _button(self, index):
        return self._window.getControl(FIRST_BUTTON_ID + index)

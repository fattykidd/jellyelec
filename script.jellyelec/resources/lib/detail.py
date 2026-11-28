"""The detail page for a movie, episode or show.

The top half: clear logo (or title), details with Ends at, resolution and audio badges,
studio and genre chips, the directors, and the plot. Under that, a row of pill buttons: Play or Resume, From start,
Trailer, Version, then Watched and Favourite toggles, which are saved to Jellyfin.

The bottom half: rows of Seasons (shows), Cast and crew, More like this and Special features.
Rows without anything in them hide themselves.
"""

from datetime import datetime, timezone

import xbmc
import xbmcgui

from resources.lib import media_details, versions
from resources.lib.api import TICKS_PER_SECOND, JellyfinError
from resources.lib.formatting import (
    directors_line,
    ends_at_text,
    episode_heading,
    format_time,
    media_badges,
    media_summary,
    spotlight_meta,
    studio_name,
)
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.listitems import (
    PLAYABLE_TYPES,
    backdrop_url,
    extra_item,
    logo_url,
    media_item,
    person_item,
    season_item,
)
from resources.lib.playback import play

# Control IDs, matching jellyelec-detail.xml.
BUTTONS = 300
PLAY_BUTTON = 301
FROM_START_BUTTON = 302
TRAILER_BUTTON = 303
VERSION_BUTTON = 304
WATCHED_BUTTON = 305
FAVOURITE_BUTTON = 306

SPECIAL_FEATURES_ROW = 400
SEASONS_ROW = 410
CAST_ROW = 420
SIMILAR_ROW = 430
ROWS = (SEASONS_ROW, CAST_ROW, SIMILAR_ROW, SPECIAL_FEATURES_ROW)

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# Who appears in Cast and crew, and how many at most.
CAST_TYPES = ("Actor", "GuestStar", "Director", "Writer")
MAX_CAST = 40

# Genre chips the skin has room for (detail_genre_1 to _4).
MAX_GENRES = 4


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
    _next_episode = None  # for shows: the episode the Play button starts
    _trailers = ()
    _extras = None  # Jellyfin data for the special features, keyed by item ID

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
            self._go_back()
            return
        # Ends at moves on with the clock; catching up on each key press is enough.
        self._show_meta()

    def onClick(self, control_id):
        if control_id == PLAY_BUTTON:
            self._play()
        elif control_id == FROM_START_BUTTON:
            self._play(from_start=True)
        elif control_id == TRAILER_BUTTON:
            play(self.client, self._trailers[0], start_seconds=0)
        elif control_id == VERSION_BUTTON:
            self._choose_version()
        elif control_id == WATCHED_BUTTON:
            self._toggle_watched()
        elif control_id == FAVOURITE_BUTTON:
            self._toggle_favourite()
        elif control_id == SEASONS_ROW:
            self._open_selected_season()
        elif control_id == SIMILAR_ROW:
            self._open_selected_similar()
        elif control_id == SPECIAL_FEATURES_ROW:
            self._play_selected_extra()

    def _go_back(self):
        """From a row: back to its start, then up to the buttons. From the buttons: close."""
        focus = self.getFocusId()
        if focus in ROWS:
            row = self.getControl(focus)
            if row.getSelectedPosition() > 0:
                row.selectItem(0)
            else:
                self._focus_buttons()
            return
        self.close()

    # Loading --------------------------------------------------------------------

    def _load(self):
        """Fetch everything the page shows. Returns False if the item couldn't be loaded."""
        if not self._fetch_item():
            _notify("Couldn't load the details for this item.")
            return False

        # The top half first, so the page is usable while the rows load.
        self._trailers = self._fetch_trailers()
        self._show_item()
        self._show_buttons()
        self._focus_buttons()

        self._show_seasons()
        self._show_cast()
        self._show_similar()
        self._show_special_features()
        return True

    def _fetch_item(self):
        """(Re)load the item from Jellyfin. Returns False if that failed."""
        try:
            self._item = self.client.get_item(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load item {self.item_id}: {error}", xbmc.LOGWARNING)
            return False
        return True

    def _fetch_trailers(self):
        if not self._item.get("LocalTrailerCount"):
            return []
        try:
            return self.client.get_local_trailers(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load trailers for {self.item_id}: {error}", xbmc.LOGWARNING)
            return []

    def _is_series(self):
        return self._item.get("Type") == "Series"

    # The top half -------------------------------------------------------------------

    def _show_item(self):
        item = self._item
        is_episode = item.get("Type") == "Episode"
        self.setProperty("title", item.get("SeriesName", "") if is_episode else item.get("Name", ""))
        self.setProperty("logo", logo_url(self.client, item) or "")
        self.setProperty("backdrop", backdrop_url(self.client, item) or "")
        self.setProperty("episode", episode_heading(item))
        self.setProperty("directors", directors_line(item))
        # The studio and genres, as chips.
        self.setProperty("detail_studio", studio_name(item))
        genres = (item.get("Genres") or [])[:MAX_GENRES]
        for number in range(1, MAX_GENRES + 1):
            self.setProperty(f"detail_genre_{number}", genres[number - 1] if number <= len(genres) else "")
        self.setProperty("plot", item.get("Overview", ""))
        self._show_meta()

        source = versions.chosen_source(item)
        media = media_details.MediaInfo(media_summary(item, source), media_badges(item, source))
        media_details.show(self, "detail", media)

    def _show_meta(self):
        """Year · rating · runtime (or time left) · community rating · Ends at."""
        if self._item is None:
            return
        parts = [spotlight_meta(self._item)]
        if self._item.get("Type") in PLAYABLE_TYPES:
            parts.append(ends_at_text(self._item, datetime.now(timezone.utc)))
        self.setProperty("meta", "  ·  ".join(part for part in parts if part))

    def _show_buttons(self):
        """Labels for the pill buttons; a button with no label is hidden by the skin."""
        if self._is_series():
            play_label, from_start = self._series_play_label(), ""
        else:
            play_label, from_start = self._video_play_labels()
        self.setProperty("play_label", play_label)
        self.setProperty("from_start_label", from_start)
        self.setProperty("trailer_label", "Trailer" if self._trailers else "")
        self.setProperty("version_label", self._version_label())

        user_data = self._item.get("UserData") or {}
        self.getControl(WATCHED_BUTTON).setSelected(bool(user_data.get("Played")))
        self.getControl(FAVOURITE_BUTTON).setSelected(bool(user_data.get("IsFavorite")))

    def _series_play_label(self):
        """A show's Play button starts the next episode to watch, or the first if it's unstarted."""
        try:
            self._next_episode = (
                self.client.get_next_up(self.item_id)
                or self.client.get_first_episode(self.item_id)
            )
        except JellyfinError as error:
            log(f"Couldn't find the next episode of {self.item_id}: {error}", xbmc.LOGWARNING)
            self._next_episode = None
        if not self._next_episode:
            return ""

        season = self._next_episode.get("ParentIndexNumber")
        episode = self._next_episode.get("IndexNumber")
        started = (self._next_episode.get("UserData") or {}).get("PlaybackPositionTicks")
        verb = "Resume" if started else "Play"
        if season is not None and episode is not None:
            return f"{verb} S{season} E{episode}"
        return f"{verb} next episode"

    def _video_play_labels(self):
        """Resume from 42:10 and From start once started; otherwise just Play."""
        ticks = self._resume_ticks()
        if ticks:
            return f"Resume from {format_time(ticks / TICKS_PER_SECOND)}", "From start"
        return "Play", ""

    def _version_label(self):
        """Version · 4K, when there's more than one version to choose from."""
        if self._is_series() or len(versions.sources(self._item)) < 2:
            return ""
        source = versions.chosen_source(self._item)
        return f"Version  ·  {versions.short_label(self._item, source)}"

    def _resume_ticks(self):
        return (self._item.get("UserData") or {}).get("PlaybackPositionTicks") or 0

    def _focus_buttons(self):
        """Focus the Play button, or the first button there is when there's nothing to play."""
        if self.getProperty("play_label"):
            self.setFocusId(PLAY_BUTTON)
        else:
            self.setFocusId(WATCHED_BUTTON)

    # The rows ---------------------------------------------------------------------

    def _show_seasons(self):
        """Shows get a row of seasons. Other items leave it empty, which hides it."""
        seasons = []
        if self._is_series():
            try:
                seasons = self.client.get_seasons(self.item_id)
            except JellyfinError as error:
                log(f"Couldn't load seasons of {self.item_id}: {error}", xbmc.LOGWARNING)
        self._fill_row(SEASONS_ROW, [season_item(self.client, season) for season in seasons])

    def _show_cast(self):
        """Actors in billing order, then the directors and writers; each person once."""
        people = [person for person in self._item.get("People") or [] if person.get("Type") in CAST_TYPES]
        people.sort(key=lambda person: person.get("Type") not in ("Actor", "GuestStar"))
        seen = set()
        items = []
        for person in people:
            key = (person.get("Id"), person.get("Type"))
            if key in seen:
                continue
            seen.add(key)
            items.append(person_item(self.client, person))
        self._fill_row(CAST_ROW, items[:MAX_CAST])

    def _show_similar(self):
        """More like this: for movies and shows (Jellyfin has little to say about episodes)."""
        similar = []
        if self._item.get("Type") in ("Movie", "Series"):
            try:
                similar = self.client.get_similar(self.item_id)
            except JellyfinError as error:
                log(f"Couldn't load titles like {self.item_id}: {error}", xbmc.LOGWARNING)
        self._fill_row(SIMILAR_ROW, [media_item(self.client, data) for data in similar])

    def _show_special_features(self):
        try:
            extras = self.client.get_special_features(self.item_id)
        except JellyfinError as error:
            log(f"Couldn't load special features for {self.item_id}: {error}", xbmc.LOGWARNING)
            extras = []
        self._extras = {extra["Id"]: extra for extra in extras}
        fallback = backdrop_url(self.client, self._item)
        self._fill_row(SPECIAL_FEATURES_ROW, [extra_item(self.client, extra, fallback) for extra in extras])

    def _fill_row(self, row_id, items):
        row = self.getControl(row_id)
        row.reset()
        row.addItems(items)

    # Buttons ----------------------------------------------------------------------

    def _play(self, from_start=False):
        if self._is_series():
            if self._next_episode:
                play(self.client, self._next_episode)
        else:
            start = 0 if from_start else self._resume_ticks() / TICKS_PER_SECOND
            play(self.client, self._item, start_seconds=start)
        self._refresh()

    def _choose_version(self):
        """Pick which version plays, from now on, for this item."""
        item_sources = versions.sources(self._item)
        current = versions.chosen_source(self._item)
        labels = [versions.version_label(self._item, source) for source in item_sources]
        choice = xbmcgui.Dialog().select("Version", labels, preselect=item_sources.index(current))
        if choice < 0:
            return
        versions.remember(self.item_id, item_sources[choice]["Id"])
        log(f"Version for {self.item_id}: {labels[choice]}")
        self._show_item()
        self._show_buttons()

    def _toggle_watched(self):
        # Kodi has already flipped the toggle; save what it now shows.
        watched = self.getControl(WATCHED_BUTTON).isSelected()
        try:
            self.client.set_played(self.item_id, watched)
        except JellyfinError as error:
            log(f"Couldn't mark {self.item_id} watched={watched}: {error}", xbmc.LOGWARNING)
            _notify("Couldn't save that to Jellyfin.")
            self.getControl(WATCHED_BUTTON).setSelected(not watched)
            return
        # Watched clears the resume point, and for a show changes the next episode and the
        # seasons' unwatched counts.
        self._refresh()
        self._show_seasons()

    def _toggle_favourite(self):
        favourite = self.getControl(FAVOURITE_BUTTON).isSelected()
        try:
            self.client.set_favorite(self.item_id, favourite)
        except JellyfinError as error:
            log(f"Couldn't set favourite={favourite} on {self.item_id}: {error}", xbmc.LOGWARNING)
            _notify("Couldn't save that to Jellyfin.")
            self.getControl(FAVOURITE_BUTTON).setSelected(not favourite)

    def _refresh(self):
        """Reload the item after playback or a change, keeping focus where it was if it's still there."""
        focus = self.getFocusId()
        if not self._fetch_item():
            return
        self._show_item()
        self._show_buttons()
        if focus == FROM_START_BUTTON or (focus == PLAY_BUTTON and not self.getProperty("play_label")):
            self._focus_buttons()

    # Rows ---------------------------------------------------------------------------

    def _open_selected_season(self):
        # Imported here because the episodes screen opens detail pages itself.
        from resources.lib.episodes import show_episodes

        row = self.getControl(SEASONS_ROW)
        selected = row.getSelectedItem()
        if selected is None:
            return
        position = row.getSelectedPosition()
        show_episodes(self.client, self._item, selected.getProperty("id"))

        # Watching episodes changes the next episode and the unwatched counts.
        self._refresh()
        self._show_seasons()
        if row.size():
            row.selectItem(min(position, row.size() - 1))
            self.setFocusId(SEASONS_ROW)

    def _open_selected_similar(self):
        selected = self.getControl(SIMILAR_ROW).getSelectedItem()
        if selected is not None:
            show_details(self.client, selected.getProperty("id"))

    def _play_selected_extra(self):
        selected = self.getControl(SPECIAL_FEATURES_ROW).getSelectedItem()
        if selected is None:
            return
        data = self._extras.get(selected.getProperty("id"))
        if data is not None:
            play(self.client, data, start_seconds=0)


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)

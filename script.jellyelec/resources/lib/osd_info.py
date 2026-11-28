"""What the player's OSD and seek bar show about the title, and the requests its buttons send.

The OSD and seek bar are skin windows (VideoOSD.xml and DialogSeekBar.xml, from
resources/skin_patch/), so they read the title's logo, name and badges from properties on
Kodi's home window, which JellyELEC sets when playback starts and clears when it ends.

The OSD's Chapters, Audio and Subtitles buttons can't run JellyELEC's code themselves; they
set the request property (key_requests.py) and close the OSD, and the running player picks
the request up within a quarter of a second.
"""

from contextlib import contextmanager

import xbmcgui

from resources.lib.formatting import age_rating, episode_heading, media_badges
from resources.lib.key_requests import HOME_WINDOW_ID
from resources.lib.kodi import ADDON_ID
from resources.lib.listitems import logo_url

PREFIX = f"{ADDON_ID}.osd_"
MAX_BADGES = 4
NAMES = ["logo", "title", "subtitle", "panel"] + [f"badge_{number}" for number in range(1, MAX_BADGES + 1)]


def show(client, data, source):
    """Fill in the OSD for a movie, episode, trailer or extra."""
    is_episode = data.get("Type") == "Episode"
    if is_episode:
        title, subtitle = data.get("SeriesName", ""), episode_heading(data)
    else:
        parts = [str(data.get("ProductionYear") or ""), age_rating(data.get("OfficialRating") or "")]
        title, subtitle = data.get("Name", ""), "  ·  ".join(part for part in parts if part)
    badges = media_badges(data, source)

    values = {"logo": logo_url(client, data) or "", "title": title, "subtitle": subtitle}
    for number in range(1, MAX_BADGES + 1):
        values[f"badge_{number}"] = badges[number - 1] if number <= len(badges) else ""
    home = xbmcgui.Window(HOME_WINDOW_ID)
    for name, value in values.items():
        home.setProperty(PREFIX + name, value)


def clear():
    home = xbmcgui.Window(HOME_WINDOW_ID)
    for name in NAMES:
        home.clearProperty(PREFIX + name)


@contextmanager
def panel_open():
    """While one of JellyELEC's panels (chapters, audio, subtitles) is over the video, the seek
    bar stays out of the way."""
    home = xbmcgui.Window(HOME_WINDOW_ID)
    home.setProperty(PREFIX + "panel", "true")
    try:
        yield
    finally:
        home.clearProperty(PREFIX + "panel")

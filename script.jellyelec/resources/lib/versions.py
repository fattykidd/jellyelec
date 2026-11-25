"""Movie versions: one movie with several files, such as a 4K and a 1080p copy.

Jellyfin groups the files into one item with several media sources. JellyELEC lists them
on the details screen and remembers the one picked for each movie, so every way of
starting playback (details, Continue Watching, the episode list) uses it.
"""

import json
import os

from resources.lib.formatting import media_summary
from resources.lib.kodi import PROFILE_PATH, log

CHOICES_FILE = os.path.join(PROFILE_PATH, "versions.json")

# Longest version name that fits on the Version button.
SHORT_LABEL_LENGTH = 14


def sources(item):
    """The item's versions, in Jellyfin's order."""
    return item.get("MediaSources") or []


def chosen_source(item):
    """The version to play: the one picked before, or else Jellyfin's first."""
    item_sources = sources(item)
    remembered = remembered_source_id(item["Id"])
    for source in item_sources:
        if source.get("Id") == remembered:
            return source
    return item_sources[0] if item_sources else None


def version_label(item, source):
    """How a version is shown: its name from the file, then what's in it.

    For example "Director's Cut  ·  4K  ·  Dolby Vision  ·  Dolby TrueHD Atmos 7.1". A name
    that only repeats the resolution ("4K") is left out.
    """
    summary = media_summary(item, source)
    name = (source.get("Name") or "").strip()
    if not name or name == item.get("Name") or summary.startswith(name):
        return summary or name or "Version"
    return f"{name}  ·  {summary}" if summary else name


def short_label(item, source):
    """A few words for the Version button: the file's version name, or else the resolution."""
    name = (source.get("Name") or "").strip()
    if name and name != item.get("Name") and len(name) <= SHORT_LABEL_LENGTH:
        return name
    summary = media_summary(item, source)
    return summary.split("  ·  ")[0] if summary else "Version"


def remembered_source_id(item_id):
    return _load_choices().get(item_id)


def remember(item_id, source_id):
    choices = _load_choices()
    choices[item_id] = source_id
    try:
        os.makedirs(PROFILE_PATH, exist_ok=True)
        with open(CHOICES_FILE, "w", encoding="utf-8") as file:
            json.dump(choices, file, indent=2)
    except OSError as error:
        log(f"Couldn't save the version choice: {error}")


def _load_choices():
    try:
        with open(CHOICES_FILE, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}

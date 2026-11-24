"""Turn Jellyfin items into Kodi ListItems that the screens can display."""

import xbmcgui

from resources.lib.api import TICKS_PER_SECOND
from resources.lib.formatting import extra_type_name, runtime_text, unwatched_text, watch_status

POSTER_HEIGHT = 450
BACKDROP_WIDTH = 1280
EXTRA_THUMB_WIDTH = 480
EPISODE_THUMB_WIDTH = 480


def library_item(library):
    """A library tile for the bar along the top."""
    item = xbmcgui.ListItem(label=library.get("Name", ""), offscreen=True)
    item.setProperty("id", library["Id"])
    item.setProperty("collection_type", library.get("CollectionType", ""))
    return item


def media_item(client, data):
    """A movie, show or episode, with artwork and basic details."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])

    art = {"poster": poster_url(client, data), "fanart": backdrop_url(client, data)}
    item.setArt({kind: url for kind, url in art.items() if url})

    tag = item.getVideoInfoTag()
    tag.setTitle(data.get("Name", ""))
    tag.setPlot(data.get("Overview", ""))
    if data.get("ProductionYear"):
        tag.setYear(int(data["ProductionYear"]))
    if data.get("RunTimeTicks"):
        tag.setDuration(int(data["RunTimeTicks"] // TICKS_PER_SECOND))

    if data.get("Type") == "Series":
        tag.setMediaType("tvshow")
    elif data.get("Type") == "Episode":
        tag.setMediaType("episode")
        tag.setTvShowTitle(data.get("SeriesName", ""))
        if data.get("ParentIndexNumber") is not None:
            tag.setSeason(int(data["ParentIndexNumber"]))
        if data.get("IndexNumber") is not None:
            tag.setEpisode(int(data["IndexNumber"]))
    else:
        tag.setMediaType("movie")

    return item


def extra_item(client, data, fallback_thumb=None):
    """A special feature tile: its own image if it has one, otherwise the parent's backdrop."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])
    item.setProperty("extra_type", extra_type_name(data.get("ExtraType")))
    if data.get("RunTimeTicks"):
        item.setProperty("runtime", runtime_text(data["RunTimeTicks"]))

    tag = data.get("ImageTags", {}).get("Primary")
    thumb = client.image_url(data["Id"], "Primary", tag, max_width=EXTRA_THUMB_WIDTH) if tag else fallback_thumb
    if thumb:
        item.setArt({"thumb": thumb})
    return item


def season_item(client, data):
    """A season poster with its unwatched count."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])
    item.setProperty("unwatched", unwatched_text(data))
    poster = poster_url(client, data)
    if poster:
        item.setArt({"poster": poster})
    return item


def episode_item(client, data):
    """An episode for the episode list: numbered title, its own picture, and watch status."""
    item = media_item(client, data)
    number = data.get("IndexNumber")
    item.setLabel(f"{number}. {data.get('Name', '')}" if number is not None else data.get("Name", ""))
    item.setProperty("status", watch_status(data))
    if data.get("RunTimeTicks"):
        item.setProperty("runtime", runtime_text(data["RunTimeTicks"]))
    thumb = episode_thumb_url(client, data)
    if thumb:
        item.setArt({"thumb": thumb})
    return item


def poster_url(client, data):
    """Episodes use their show's poster; seasons without their own fall back to it too."""
    series_poster = None
    if data.get("SeriesId") and data.get("SeriesPrimaryImageTag"):
        series_poster = client.image_url(
            data["SeriesId"], "Primary", data["SeriesPrimaryImageTag"], max_height=POSTER_HEIGHT
        )
    if data.get("Type") == "Episode" and series_poster:
        return series_poster

    tag = data.get("ImageTags", {}).get("Primary")
    if tag:
        return client.image_url(data["Id"], "Primary", tag, max_height=POSTER_HEIGHT)
    return series_poster


def episode_thumb_url(client, data):
    """An episode's own still image, falling back to its show's backdrop."""
    tag = data.get("ImageTags", {}).get("Primary")
    if tag:
        return client.image_url(data["Id"], "Primary", tag, max_width=EPISODE_THUMB_WIDTH)
    return backdrop_url(client, data)


def backdrop_url(client, data):
    """The item's own backdrop, or its parent's (an episode borrows its show's)."""
    if data.get("BackdropImageTags"):
        return client.image_url(
            data["Id"], "Backdrop", data["BackdropImageTags"][0], max_width=BACKDROP_WIDTH
        )
    if data.get("ParentBackdropImageTags") and data.get("ParentBackdropItemId"):
        return client.image_url(
            data["ParentBackdropItemId"],
            "Backdrop",
            data["ParentBackdropImageTags"][0],
            max_width=BACKDROP_WIDTH,
        )
    return None

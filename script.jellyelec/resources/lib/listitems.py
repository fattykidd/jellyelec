"""Turn Jellyfin items into Kodi ListItems that the screens can display."""

import xbmcgui

TICKS_PER_SECOND = 10_000_000
POSTER_HEIGHT = 450
BACKDROP_WIDTH = 1280


def library_item(library):
    """A library tile for the bar along the top."""
    item = xbmcgui.ListItem(label=library.get("Name", ""), offscreen=True)
    item.setProperty("id", library["Id"])
    item.setProperty("collection_type", library.get("CollectionType", ""))
    return item


def media_item(client, data):
    """A movie or episode, with artwork and the details the spotlight shows."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])

    art = {"poster": _poster_url(client, data), "fanart": _backdrop_url(client, data)}
    item.setArt({kind: url for kind, url in art.items() if url})

    tag = item.getVideoInfoTag()
    tag.setTitle(data.get("Name", ""))
    tag.setPlot(data.get("Overview", ""))
    if data.get("ProductionYear"):
        tag.setYear(int(data["ProductionYear"]))
    if data.get("RunTimeTicks"):
        tag.setDuration(int(data["RunTimeTicks"] // TICKS_PER_SECOND))

    if data.get("Type") == "Episode":
        tag.setMediaType("episode")
        tag.setTvShowTitle(data.get("SeriesName", ""))
        if data.get("ParentIndexNumber") is not None:
            tag.setSeason(int(data["ParentIndexNumber"]))
        if data.get("IndexNumber") is not None:
            tag.setEpisode(int(data["IndexNumber"]))
    else:
        tag.setMediaType("movie")

    return item


def _poster_url(client, data):
    """Episodes use their show's poster; everything else uses its own."""
    if data.get("Type") == "Episode" and data.get("SeriesPrimaryImageTag"):
        return client.image_url(
            data["SeriesId"], "Primary", data["SeriesPrimaryImageTag"], max_height=POSTER_HEIGHT
        )
    tag = data.get("ImageTags", {}).get("Primary")
    if tag:
        return client.image_url(data["Id"], "Primary", tag, max_height=POSTER_HEIGHT)
    return None


def _backdrop_url(client, data):
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

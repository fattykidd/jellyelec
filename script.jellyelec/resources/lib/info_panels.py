"""Panels opened from a detail page's buttons: Media info and Artwork.

Media info shows the title's file and each of its tracks as a row of cards (media_info.py
works out what goes on them). Artwork shows every picture Jellyfin has for the title, large,
with a strip of thumbnails to move through them. Back closes either.
"""

import xbmc
import xbmcgui

from resources.lib import media_details, media_info
from resources.lib.api import JellyfinError
from resources.lib.formatting import media_badges, media_summary
from resources.lib.kodi import ADDON_PATH, log

# Control IDs, matching jellyelec-mediainfo.xml and jellyelec-artwork.xml.
CARDS = 1200
THUMBNAILS = 1300

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# Names for Jellyfin's image types, in the order the viewer shows them. Chapter pictures
# aren't artwork, so they're left out.
IMAGE_TYPE_NAMES = {
    "Primary": "Poster",
    "Logo": "Logo",
    "Backdrop": "Backdrop",
    "Thumb": "Thumb",
    "Banner": "Banner",
    "Art": "Clear art",
    "Disc": "Disc",
    "Box": "Box",
    "BoxRear": "Box back",
    "Screenshot": "Screenshot",
    "Menu": "Menu",
}
# Thumbnails in the strip, and the large picture (sharp on a 4K screen).
THUMBNAIL_HEIGHT = 300
FULL_WIDTH = 3840

# The key on a card, dimmed, before its value.
ROW_FORMAT = "[COLOR FF8D90A0]{}[/COLOR]   {}"


def show_media_info(item, source):
    """The Media info panel for one version of an item."""
    window = MediaInfoWindow("jellyelec-mediainfo.xml", ADDON_PATH, "Default", "1080i")
    window.item = item
    window.source = source
    window.doModal()
    del window


def show_artwork(client, item):
    """The artwork viewer. Says so, and doesn't open, if the title has no artwork."""
    try:
        images = client.get_images(item["Id"])
    except JellyfinError as error:
        log(f"Couldn't list the artwork of {item['Id']}: {error}", xbmc.LOGWARNING)
        images = []
    pictures = _sorted_pictures(images)
    if not pictures:
        xbmcgui.Dialog().notification(item.get("Name", ""), "No artwork for this title.")
        return

    window = ArtworkWindow("jellyelec-artwork.xml", ADDON_PATH, "Default", "1080i")
    window.title = item.get("Name", "")
    window.items = [_picture_item(client, item, picture, pictures) for picture in pictures]
    window.doModal()
    del window


class MediaInfoWindow(xbmcgui.WindowXMLDialog):
    """Set item and source before calling doModal()."""

    item = None
    source = None

    def onInit(self):
        self.setProperty("title", self.item.get("Name", ""))
        media = media_details.MediaInfo(media_summary(self.item, self.source), media_badges(self.item, self.source))
        media_details.show(self, "detail", media)

        cards = self.getControl(CARDS)
        cards.reset()
        cards.addItems([_card_item(card) for card in media_info.cards(self.item, self.source)])
        self.setFocusId(CARDS)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()


class ArtworkWindow(xbmcgui.WindowXMLDialog):
    """Set title and items before calling doModal()."""

    title = ""
    items = ()

    def onInit(self):
        self.setProperty("title", self.title)
        strip = self.getControl(THUMBNAILS)
        strip.reset()
        strip.addItems(self.items)
        self.setFocusId(THUMBNAILS)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()


# Helpers ----------------------------------------------------------------------------

def _card_item(card):
    item = xbmcgui.ListItem(label=card.heading, offscreen=True)
    item.setProperty("subheading", card.subheading)
    item.setProperty("body", "[CR]".join(ROW_FORMAT.format(name, value) for name, value in card.rows))
    return item


def _sorted_pictures(images):
    """The item's artwork in IMAGE_TYPE_NAMES order, then by number within a type."""
    order = list(IMAGE_TYPE_NAMES)
    pictures = [image for image in images if image.get("ImageType") in IMAGE_TYPE_NAMES]
    return sorted(pictures, key=lambda image: (order.index(image["ImageType"]), image.get("ImageIndex") or 0))


def _picture_item(client, item, picture, pictures):
    """One picture: its thumbnail, the large version, and "Backdrop 3 of 12  ·  3840 × 2160"."""
    kind = picture["ImageType"]
    index = picture.get("ImageIndex") or 0
    tag = picture.get("ImageTag")
    same_kind = [other for other in pictures if other["ImageType"] == kind]

    name = IMAGE_TYPE_NAMES[kind]
    if item.get("Type") == "Episode" and kind == "Primary":
        name = "Still"
    if len(same_kind) > 1:
        name = f"{name} {same_kind.index(picture) + 1} of {len(same_kind)}"

    entry = xbmcgui.ListItem(label=name, offscreen=True)
    if picture.get("Width") and picture.get("Height"):
        entry.setProperty("size", f"{picture['Width']} × {picture['Height']}")
    entry.setArt({
        "thumb": client.image_url(item["Id"], kind, tag, max_height=THUMBNAIL_HEIGHT, index=index),
        "full": client.image_url(item["Id"], kind, tag, max_width=FULL_WIDTH, index=index),
    })
    return entry

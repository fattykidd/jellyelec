#!/usr/bin/env python3
"""Draw the plain shapes JellyELEC's screens are built from: fades, pills, rings, masks and icons.

Writes PNGs into the add-on's media folder. Run it again after changing a shape:

    python3 tools/make_textures.py

Everything is white (or white with see-through parts), so the screens colour each shape with
<colordiffuse>. Shapes are drawn four times larger and scaled down, for smooth edges.

Needs Pillow (pip install pillow).
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

MEDIA = Path(__file__).resolve().parent.parent / "script.jellyelec" / "resources" / "skins" / "Default" / "media"
SCALE = 4
WHITE = (255, 255, 255, 255)

# The screens' background colour, which the fades blend into.
BACKGROUND = (11, 12, 17)


def save(image, name):
    image.save(MEDIA / name, optimize=True)
    print(f"  {name}  {image.width}x{image.height}")


def smooth(width, height, draw_shape):
    """Draw at SCALE times the size with draw_shape(draw, scale), then scale down."""
    big = Image.new("RGBA", (width * SCALE, height * SCALE), (255, 255, 255, 0))
    draw_shape(ImageDraw.Draw(big), SCALE)
    return big.resize((width, height), Image.LANCZOS)


# Fades ---------------------------------------------------------------------------

def fade(length, stops, horizontal):
    """A strip of the background colour whose opacity follows stops: [(position 0-1, alpha 0-255)]."""
    strip = Image.new("RGBA", (length, 1) if horizontal else (1, length))
    for index in range(length):
        position = index / (length - 1)
        for (start, start_alpha), (end, end_alpha) in zip(stops, stops[1:]):
            if start <= position <= end:
                share = (position - start) / (end - start) if end > start else 0
                alpha = round(start_alpha + (end_alpha - start_alpha) * share)
                break
        strip.putpixel((index, 0) if horizontal else (0, index), (*BACKGROUND, alpha))
    return strip.resize((length, 4) if horizontal else (4, length))


# Shapes --------------------------------------------------------------------------

def rounded_box(size, radius):
    return smooth(size, size, lambda draw, s: draw.rounded_rectangle(
        (0, 0, size * s - 1, size * s - 1), radius=radius * s, fill=WHITE))


def rounded_ring(size, radius, thickness):
    return smooth(size, size, lambda draw, s: draw.rounded_rectangle(
        (0, 0, size * s - 1, size * s - 1), radius=radius * s, outline=WHITE, width=thickness * s))


def library_focus_pill():
    """The focused library: a Jellyfin-blue outline with a faint blue fill, 4px clear above and
    below so it sits inside the 64px-tall bar. Coloured here, as it's used as a button texture."""
    blue = (0, 164, 220)
    def draw_pill(draw, s):
        box = (0, 4 * s, 64 * s - 1, 60 * s - 1)
        draw.rounded_rectangle(box, radius=28 * s, fill=(*blue, 46), outline=(*blue, 255), width=3 * s)
    return smooth(64, 64, draw_pill)


def library_underline():
    """The current library when the bar isn't focused: a bar along the bottom, 22px in from
    each end (stretched with border="22,0,22,0"). White, coloured with colordiffuse."""
    def draw_line(draw, s):
        draw.rounded_rectangle((22 * s, 56 * s, 42 * s - 1, 60 * s - 1), radius=2 * s, fill=WHITE)
    return smooth(64, 64, draw_line)


def card_mask(width, height, radius):
    return smooth(width, height, lambda draw, s: draw.rounded_rectangle(
        (0, 0, width * s - 1, height * s - 1), radius=radius * s, fill=WHITE))


def cogs_icon(size):
    """Settings: three cogs in a triangle, as in the v2 home screen design."""
    def draw_cogs(draw, s):
        unit = size * s / 24  # drawn on a 24-unit grid, like the design's SVG
        line = round(1.5 * unit)
        for cx, cy, turn in ((12, 6.8, 0), (7.4, 15.2, 22.5), (16.6, 15.2, 22.5)):
            x, y = cx * unit, cy * unit
            body, hole, tooth = 3 * unit, 1 * unit, 4.1 * unit
            draw.ellipse((x - body, y - body, x + body, y + body), outline=WHITE, width=line)
            draw.ellipse((x - hole, y - hole, x + hole, y + hole), outline=WHITE, width=line)
            for k in range(8):
                angle = math.radians(turn + k * 45)
                draw.line(
                    (x + body * math.cos(angle), y + body * math.sin(angle),
                     x + tooth * math.cos(angle), y + tooth * math.sin(angle)),
                    fill=WHITE, width=line,
                )
    return smooth(size, size, draw_cogs)


def main():
    print(f"Writing to {MEDIA}")
    # Over the backdrop: solid on the left, clear by just past the middle; clear at the top,
    # solid at the bottom, where the rows start.
    save(fade(512, [(0, 255), (0.22, 217), (0.55, 0), (1, 0)], horizontal=True), "jellyelec-fade-left.png")
    save(fade(512, [(0, 0), (1, 255)], horizontal=False), "jellyelec-fade-bottom.png")
    # Stretchable with <texture border="...">: pills and pill outlines for the library bar,
    # rings for focused cards.
    save(rounded_box(64, 32), "jellyelec-pill.png")
    save(rounded_ring(64, 18, 4), "jellyelec-ring.png")
    save(rounded_ring(64, 32, 3), "jellyelec-pill-ring.png")
    save(library_focus_pill(), "jellyelec-library-focus.png")
    save(library_underline(), "jellyelec-library-underline.png")
    # Media badges (4K, DOLBY VISION...): an outline, stretched with border="10".
    save(smooth(64, 36, lambda draw, s: draw.rounded_rectangle(
        (0, 0, 64 * s - 1, 36 * s - 1), radius=8 * s, outline=WHITE, width=2 * s)), "jellyelec-badge.png")
    # Rounded corners for posters, used as <texture diffuse="...">.
    save(card_mask(180, 270, 12), "jellyelec-mask-poster.png")
    save(card_mask(384, 216, 14), "jellyelec-mask-landscape.png")
    save(cogs_icon(96), "jellyelec-icon-settings.png")


if __name__ == "__main__":
    main()

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


# Weather -----------------------------------------------------------------------------

def weather_icons():
    """Simple white weather glyphs on a 24-unit grid, drawn filled so they read at 36px."""
    def sun(draw, u, cx=12, cy=12, r=4.2, rays=True):
        draw.ellipse(((cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u), fill=WHITE)
        if rays:
            for k in range(8):
                a = math.radians(k * 45)
                draw.line(((cx + 6.4 * math.cos(a)) * u, (cy + 6.4 * math.sin(a)) * u,
                           (cx + 8.8 * math.cos(a)) * u, (cy + 8.8 * math.sin(a)) * u),
                          fill=WHITE, width=round(1.6 * u))

    def moon(draw, u, cx=12, cy=12, r=7):
        draw.ellipse(((cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u), fill=WHITE)
        draw.ellipse(((cx - r + 4.5) * u, (cy - r - 2.5) * u, (cx + r + 4.5) * u, (cy + r - 2.5) * u),
                     fill=(255, 255, 255, 0))

    def cloud(draw, u, dx=0.0, dy=0.0, gap=False):
        shapes = [(4, 10, 12, 18), (8, 5, 17, 14), (13, 9, 21, 17)]
        fill = (255, 255, 255, 0) if gap else WHITE
        grow = 1.4 if gap else 0
        for x0, y0, x1, y1 in shapes:
            draw.ellipse(((x0 + dx - grow) * u, (y0 + dy - grow) * u, (x1 + dx + grow) * u, (y1 + dy + grow) * u), fill=fill)
        draw.rectangle(((8 + dx - grow) * u, (13 + dy - grow) * u, (17 + dx + grow) * u, (18 + dy + grow) * u), fill=fill)

    def drops(draw, u):
        for x in (8, 12, 16):
            draw.line(((x + 1) * u, 19.5 * u, x * u, 22.5 * u), fill=WHITE, width=round(1.6 * u))

    def flakes(draw, u):
        for x in (8, 12, 16):
            draw.ellipse(((x - 1.1) * u, 20 * u, (x + 1.1) * u, 22.2 * u), fill=WHITE)

    def bolt(draw, u):
        draw.polygon([(13 * u, 17 * u), (9.5 * u, 21 * u), (12 * u, 21 * u), (10.5 * u, 24 * u),
                      (15 * u, 19.5 * u), (12.5 * u, 19.5 * u), (14 * u, 17 * u)], fill=WHITE)

    def lines(draw, u, rows, lengths):
        for y, (x0, x1) in zip(rows, lengths):
            draw.line((x0 * u, y * u, x1 * u, y * u), fill=WHITE, width=round(1.8 * u))

    def up(cloud_dy=-3):
        return lambda draw, u: cloud(draw, u, dy=cloud_dy)

    icons = {
        "sun": lambda d, u: sun(d, u),
        "moon": lambda d, u: moon(d, u),
        "cloud": lambda d, u: cloud(d, u, dy=1),
        "partly": lambda d, u: (sun(d, u, 9, 9, 3.6, rays=False), cloud(d, u, 2, 4, gap=True), cloud(d, u, 2, 4)),
        "partly-night": lambda d, u: (moon(d, u, 9, 9, 5.5), cloud(d, u, 2, 4, gap=True), cloud(d, u, 2, 4)),
        "rain": lambda d, u: (up()(d, u), drops(d, u)),
        "snow": lambda d, u: (up()(d, u), flakes(d, u)),
        "storm": lambda d, u: (up(-4)(d, u), bolt(d, u)),
        "fog": lambda d, u: lines(d, u, (7, 12, 17), ((4, 20), (2, 18), (6, 22))),
        "wind": lambda d, u: lines(d, u, (8, 12, 16), ((3, 17), (5, 21), (3, 14))),
    }
    for name, draw_icon in icons.items():
        def paint(draw, s, draw_icon=draw_icon):
            draw_icon(draw, 96 * s / 24)
        save(smooth(96, 96, paint), f"jellyelec-weather-{name}.png")


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
    weather_icons()


if __name__ == "__main__":
    main()

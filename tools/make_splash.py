"""Draw JellyELEC's splash artwork: a jellyfish, the wordmark, and the still splash.

    python3 tools/make_splash.py

Writes into the add-on's skin media folder:
  jellyelec-jellyfish.png  one jellyfish, drawn large; the screens show it at several sizes
  jellyelec-wordmark.png   "JellyELEC" and its accent bar on a transparent background
  jellyelec-splash.png     the still splash: background, jellyfish where the animation
                           starts, then the wordmark (used for the boot and Kodi splashes)

The jellyfish positions below must match the animated screens (jellyelec-splash.xml in the
add-on and image/skin/Startup.xml), so the still splash hands over to them seamlessly.

Needs Pillow and the Inter font (Inter-Bold.otf, SIL Open Font License).
"""

import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

MEDIA_DIR = os.path.join(os.path.dirname(__file__), "..", "script.jellyelec", "resources", "skins", "Default", "media")
FONT_PATHS = ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/inter/Inter-Bold.otf")

SCREEN = (1920, 1080)
BACKGROUND = (0x10, 0x14, 0x18)
WHITE = (255, 255, 255)
ACCENT = (0xAA, 0x5C, 0xC3)

# The jellyfish as drawn, and where each one sits on the screen: left, top, width, height.
JELLYFISH_SIZE = (300, 480)
JELLYFISH_PLACES = (
    (250, 330, 225, 360),   # left
    (1430, 130, 270, 432),  # right, the largest
    (1110, 640, 150, 240),  # small, lower right
)

SUPERSAMPLE = 3  # drawn larger, then scaled down, for smooth edges


def draw_jellyfish():
    """One translucent jellyfish: a glowing bell, frilled arms and trailing tentacles."""
    width, height = (size * SUPERSAMPLE for size in JELLYFISH_SIZE)
    scale = SUPERSAMPLE
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    bell_left, bell_right = 22 * scale, 278 * scale
    bell_top, bell_bottom = 40 * scale, 190 * scale
    centre_x = (bell_left + bell_right) / 2

    # Tentacles: thin wavy lines from the bell's rim, fading out as they trail.
    for index in range(9):
        start_x = bell_left + (bell_right - bell_left) * (index + 0.5) / 9
        phase = index * 0.9
        points = []
        for step in range(60):
            t = step / 59
            y = bell_bottom - 6 * scale + t * (height - bell_bottom - 10 * scale)
            x = start_x + math.sin(t * 5 + phase) * 10 * scale * t + (start_x - centre_x) * 0.25 * t
            points.append((x, y))
        for step in range(len(points) - 1):
            alpha = int(150 * (1 - step / len(points)) ** 1.4)
            draw.line([points[step], points[step + 1]], fill=(*ACCENT, alpha), width=2 * scale)

    # Oral arms: a few wider, frilled ribbons under the middle of the bell.
    for offset, phase in ((-28, 0.0), (0, 1.7), (28, 3.1)):
        for step in range(45):
            t = step / 44
            y = bell_bottom - 10 * scale + t * 230 * scale
            x = centre_x + offset * scale + math.sin(t * 7 + phase) * 14 * scale * (0.3 + t)
            radius = (11 - 7 * t) * scale
            alpha = int(120 * (1 - t) ** 1.2)
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=(200, 150, 220, alpha))

    # The bell: a see-through dome with a scalloped rim. Its edge is brighter than its
    # middle, as light catches the rim of a real jellyfish.
    dome_box = [bell_left, bell_top, bell_right, bell_bottom * 2 - bell_top]
    middle_y = (bell_top + bell_bottom * 2 - bell_top) / 2
    scallops = 8
    scallop_width = (bell_right - bell_left) / scallops

    def bell_shape(fill):
        shape = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shape_draw = ImageDraw.Draw(shape)
        shape_draw.pieslice(dome_box, 180, 360, fill=fill)
        for index in range(scallops):
            left = bell_left + index * scallop_width
            shape_draw.ellipse([left, middle_y - 12 * scale, left + scallop_width, middle_y + 12 * scale], fill=fill)
        return shape

    bell = bell_shape((*ACCENT, 105))
    # The rim: the shape's outline, found by taking away a shrunken copy of the shape.
    outline = bell_shape((*ACCENT, 255)).getchannel("A")
    interior = outline.filter(ImageFilter.GaussianBlur(10 * scale)).point(lambda a: 255 if a > 200 else 0)
    rim_alpha = ImageChops.subtract(outline, interior).filter(ImageFilter.GaussianBlur(2 * scale))
    rim = Image.new("RGBA", (width, height), (215, 160, 235, 0))
    rim.putalpha(rim_alpha.point(lambda a: int(a * 0.85)))
    bell = Image.alpha_composite(bell, rim)

    # A soft highlight near the top, so the bell looks rounded and lit from above.
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).ellipse(
        [centre_x - 70 * scale, bell_top + 25 * scale, centre_x + 30 * scale, bell_top + 95 * scale],
        fill=(255, 255, 255, 110),
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(14 * scale))
    bell = Image.alpha_composite(bell, Image.composite(highlight, Image.new("RGBA", bell.size), bell))

    # A glow around the whole bell.
    glow = bell.filter(ImageFilter.GaussianBlur(18 * scale))
    layer = Image.alpha_composite(layer, glow)
    layer = Image.alpha_composite(layer, bell)
    return layer.resize(JELLYFISH_SIZE, Image.LANCZOS)


def draw_wordmark():
    """'Jelly' in white and 'ELEC' in the accent colour, with the accent bar beneath."""
    font_path = next(path for path in FONT_PATHS if os.path.exists(path))
    font = ImageFont.truetype(font_path, 150)
    layer = Image.new("RGBA", SCREEN, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left_text, right_text = "Jelly", "ELEC"
    left_width = draw.textlength(left_text, font=font)
    right_width = draw.textlength(right_text, font=font)
    ascent, descent = font.getmetrics()
    x = (SCREEN[0] - (left_width + right_width)) / 2
    y = (SCREEN[1] - (ascent + descent)) / 2 - 30
    draw.text((x, y), left_text, font=font, fill=WHITE)
    draw.text((x + left_width, y), right_text, font=font, fill=ACCENT)
    bar_top = y + ascent + descent + 36
    draw.rectangle([(SCREEN[0] - 160) / 2, bar_top, (SCREEN[0] + 160) / 2, bar_top + 6], fill=ACCENT)
    return layer


def draw_still_splash(jellyfish, wordmark):
    """The splash as the animation's first frame: background, jellyfish, then the wordmark."""
    splash = Image.new("RGBA", SCREEN, (*BACKGROUND, 255))
    for left, top, width, height in JELLYFISH_PLACES:
        splash.alpha_composite(jellyfish.resize((width, height), Image.LANCZOS), (left, top))
    splash.alpha_composite(wordmark)
    return splash.convert("RGB")


def main():
    jellyfish = draw_jellyfish()
    wordmark = draw_wordmark()
    jellyfish.save(os.path.join(MEDIA_DIR, "jellyelec-jellyfish.png"), optimize=True)
    wordmark.save(os.path.join(MEDIA_DIR, "jellyelec-wordmark.png"), optimize=True)
    draw_still_splash(jellyfish, wordmark).save(os.path.join(MEDIA_DIR, "jellyelec-splash.png"), optimize=True)
    print(f"Wrote the splash artwork to {os.path.normpath(MEDIA_DIR)}")


if __name__ == "__main__":
    main()

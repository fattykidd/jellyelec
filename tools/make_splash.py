"""Draw JellyELEC's splash artwork: a jellyfish, the wordmark, and the still splash.

    python3 tools/make_splash.py

Writes into the add-on's skin media folder:
  jellyelec-jellyfish.png  one jellyfish, drawn large; the screens show it at several sizes
  jellyelec-wordmark.png   "JellyELEC" and its accent bar on a transparent background
  jellyelec-splash.png     the still splash: background, jellyfish where the animation
                           starts, then the wordmark (used for the boot and Kodi splashes)

The jellyfish positions below must match the animated screens (jellyelec-splash.xml in the
add-on and image/skin/Startup.xml), so the still splash hands over to them seamlessly.

Needs Pillow, NumPy and the Inter font (Inter-Bold.otf, SIL Open Font License).
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
    """One translucent jellyfish, after a moon jelly.

    A wide bell that's clear in the middle and bright at the edges, with faint channels
    running to the rim and four glowing rings inside; a fringe of short tentacles round
    the rim and a skirt of long, fine ones trailing below; and a soft glow over it all.
    """
    width, height = (size * SUPERSAMPLE for size in JELLYFISH_SIZE)
    scale = SUPERSAMPLE
    random = np.random.default_rng(7)  # fixed, so the drawing is the same every time

    centre_x = width / 2
    half_width = 138 * scale
    bell_top, rim_y = 60 * scale, 165 * scale
    bell_height = rim_y - bell_top

    # The bell, worked out pixel by pixel. r is 0 at the top-centre and 1 at the edge.
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    dx = (xs - centre_x) / half_width
    dy = (ys - rim_y) / bell_height
    r = np.sqrt(dx ** 2 + dy ** 2)
    angle = np.arctan2(dy, dx)  # -pi at the left of the rim, -pi/2 at the top, 0 at the right
    # The rim isn't a clean line: it's gently scalloped, but only near the bottom edge;
    # the top of the bell stays smooth.
    near_rim = np.cos(angle) ** 6
    edge = 1 + 0.03 * np.cos(angle * 16) * near_rim
    inside = (r <= edge) & (ys <= rim_y + 6 * scale)
    closeness = np.clip(r / edge, 0, 1)  # 0 at the top, 1 at the edge

    alpha = 40 + 175 * closeness ** 3
    # Faint channels running from the top to the rim.
    alpha += 25 * (np.cos(angle * 24) > 0.92) * closeness
    deep, pale = np.array([105, 55, 150]), np.array([228, 190, 248])
    colour = deep + (pale - deep) * (closeness[..., None] ** 2)
    bell = np.zeros((height, width, 4), np.float32)
    bell[..., :3] = colour
    bell[..., 3] = np.where(inside, alpha, 0)

    # Four rings inside the bell, in a clover, glowing pink.
    ring_y = bell_top + bell_height * 0.62
    for ring_x, ring_dy in ((-42, 0), (42, 0), (-14, -12), (14, -12)):
        rx = (xs - (centre_x + ring_x * scale)) / (17 * scale)
        ry = (ys - (ring_y + ring_dy * scale)) / (11 * scale)
        band = np.exp(-((np.sqrt(rx ** 2 + ry ** 2) - 1) ** 2) / 0.04)
        ring_alpha = band * 115 * inside
        mix = ring_alpha / 255
        bell[..., :3] = bell[..., :3] * (1 - mix[..., None]) + np.array([250, 175, 225]) * mix[..., None]
        bell[..., 3] = np.maximum(bell[..., 3], ring_alpha)

    bell_image = Image.fromarray(np.clip(bell, 0, 255).astype(np.uint8), "RGBA")
    bell_image = bell_image.filter(ImageFilter.GaussianBlur(0.8 * scale))

    # Tentacles: a fringe of short ones round the rim, and long, fine ones trailing below.
    tentacles = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for count, shortest, longest, base_alpha in ((70, 0.06, 0.16, 120), (22, 0.45, 1.0, 150)):
        for _ in range(count):
            across = random.uniform(-0.97, 0.97)
            start_x = centre_x + across * half_width
            start_y = rim_y - (1 - (1 - across ** 2) ** 0.5) * bell_height * 0.15
            length = random.uniform(shortest, longest) * (height - rim_y)
            phase, sway = random.uniform(0, 6.3), random.uniform(4, 10) * scale
            strand = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            strand_draw = ImageDraw.Draw(strand)
            previous = (start_x, start_y)
            for step in range(1, 50):
                t = step / 49
                point = (
                    start_x + across * 30 * scale * t ** 1.4 + math.sin(t * 5 + phase) * sway * t,
                    start_y + t * length,
                )
                fade = int(base_alpha * (1 - t) ** 1.3)
                strand_draw.line([previous, point], fill=(222, 185, 245, fade), width=max(1, int(1.2 * scale)))
                previous = point
            tentacles = Image.alpha_composite(tentacles, strand)

    jellyfish = Image.alpha_composite(tentacles, bell_image)

    # A soft bioluminescent glow over the whole animal.
    glow = jellyfish.filter(ImageFilter.GaussianBlur(14 * scale))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.7)))
    jellyfish = Image.alpha_composite(glow, jellyfish)
    return jellyfish.resize(JELLYFISH_SIZE, Image.LANCZOS)


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

"""Build JellyELEC's splash pictures from the artwork in artwork/.

    python3 tools/make_splash.py

Writes these 1920×1080 pictures into the add-on's skin media folder:
  jellyelec-ocean.png      the background
  jellyelec-rays.png       extra light rays, faded in and out over the ocean's own
  jellyelec-triangle.png   the circuit triangle, see-through, toned down so the jellyfish leads
  jellyelec-jellyfish.png  the jellyfish, see-through
  jellyelec-wordmark.png   "JellyELEC" and its accent bar, below the triangle
  jellyelec-splash.png     all of the above in one still picture: the boot and Kodi splash

Every layer is full screen and lined up, so the animated screens (jellyelec-splash.xml in the
add-on, resources/skin_patch/Startup.xml) just stack them. The still splash is the animation's first
frame, so it hands over to them without a jump.

Needs Pillow, NumPy and the Inter font (Inter-Bold.otf, SIL Open Font License).
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ARTWORK_DIR = os.path.join(REPO_DIR, "artwork")
MEDIA_DIR = os.path.join(REPO_DIR, "script.jellyelec", "resources", "skins", "Default", "media")
FONT_PATHS = ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/inter/Inter-Bold.otf")

SCREEN = (1920, 1080)
WHITE = (255, 255, 255)
ACCENT = (0xAA, 0x5C, 0xC3)

# How bright the triangle is, so the jellyfish stands in front of it.
TRIANGLE_STRENGTH = 0.68
# How bright the extra light rays are at their brightest.
RAYS_STRENGTH = 0.22
# Picture brightness below this counts as black (upscaling leaves faint speckles there).
BLACK_LEVEL = 0.03

WORDMARK_FONT_SIZE = 84
WORDMARK_CENTRE_Y = 905


def load_artwork(name):
    """An artwork picture, scaled to the screen."""
    return Image.open(os.path.join(ARTWORK_DIR, name)).convert("RGB").resize(SCREEN, Image.LANCZOS)


def glow_layer(picture, strength=1.0):
    """Turn glowing art on black into a see-through layer.

    Each pixel's brightness becomes how solid it is, and its colour is brightened to make up
    for that, so laid over the ocean it glows the same as it did on black.
    """
    rgb = np.asarray(picture).astype(np.float32) / 255
    alpha = rgb.max(axis=2, keepdims=True)
    colour = np.where(alpha > 0.01, rgb / np.maximum(alpha, 1e-3), 0)
    alpha = np.clip((alpha - BLACK_LEVEL) / (1 - BLACK_LEVEL), 0, 1) * strength
    layer = np.concatenate([colour, alpha], axis=2)
    return Image.fromarray((layer * 255).astype(np.uint8), "RGBA")


def draw_rays():
    """Soft beams of light fanning down from the top centre, to shimmer over the ocean."""
    width, height = SCREEN
    layer = Image.new("RGBA", SCREEN, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    source_x = width / 2
    for offset, spread, brightness in ((-330, 70, 0.8), (-140, 55, 1.0), (60, 80, 0.9), (260, 60, 0.7)):
        top = (source_x + offset * 0.25, -40)
        bottom_left = (source_x + offset - spread, height * 0.8)
        bottom_right = (source_x + offset + spread, height * 0.8)
        alpha = int(255 * RAYS_STRENGTH * brightness)
        draw.polygon([top, bottom_right, bottom_left], fill=(150, 200, 230, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(45))

    # Fade the beams out towards the bottom, as light does in deep water.
    fade = np.linspace(1.0, 0.0, height) ** 1.6
    pixels = np.asarray(layer).astype(np.float32)
    pixels[..., 3] *= fade[:, None]
    return Image.fromarray(pixels.astype(np.uint8), "RGBA")


def draw_wordmark():
    """'Jelly' in white and 'ELEC' in the accent colour, with the accent bar beneath."""
    font_path = next(path for path in FONT_PATHS if os.path.exists(path))
    font = ImageFont.truetype(font_path, WORDMARK_FONT_SIZE)
    layer = Image.new("RGBA", SCREEN, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left_text, right_text = "Jelly", "ELEC"
    left_width = draw.textlength(left_text, font=font)
    right_width = draw.textlength(right_text, font=font)
    ascent, descent = font.getmetrics()
    x = (SCREEN[0] - (left_width + right_width)) / 2
    y = WORDMARK_CENTRE_Y - (ascent + descent) / 2
    draw.text((x, y), left_text, font=font, fill=WHITE)
    draw.text((x + left_width, y), right_text, font=font, fill=ACCENT)
    bar_top = y + ascent + descent + 18
    draw.rectangle([(SCREEN[0] - 90) / 2, bar_top, (SCREEN[0] + 90) / 2, bar_top + 4], fill=ACCENT)
    return layer


def main():
    layers = {
        "jellyelec-ocean.png": load_artwork("ocean.png").convert("RGBA"),
        "jellyelec-rays.png": draw_rays(),
        "jellyelec-triangle.png": glow_layer(load_artwork("triangle.png"), TRIANGLE_STRENGTH),
        "jellyelec-jellyfish.png": glow_layer(load_artwork("jellyfish.png")),
        "jellyelec-wordmark.png": draw_wordmark(),
    }
    still = Image.new("RGBA", SCREEN)
    for name, layer in layers.items():
        layer.save(os.path.join(MEDIA_DIR, name), optimize=True)
        still.alpha_composite(layer)
    still.convert("RGB").save(os.path.join(MEDIA_DIR, "jellyelec-splash.png"), optimize=True)
    print(f"Wrote the splash pictures to {os.path.normpath(MEDIA_DIR)}")


if __name__ == "__main__":
    main()

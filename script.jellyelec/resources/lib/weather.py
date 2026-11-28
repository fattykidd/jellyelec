"""The weather icon in the top bar.

Kodi's weather add-ons report the conditions as a code (Weather.FanartCode), numbered the way
Yahoo's weather service numbered them: 0 to 47, such as 32 for sunny or 11 for showers.
JellyELEC draws its own simple icons for them (tools/make_textures.py) to match its look,
rather than Kodi's large colourful ones.
"""

import os

import xbmc

# Each icon, and the condition codes it stands for.
ICON_CODES = {
    "storm": (0, 1, 2, 3, 4, 37, 38, 39, 45, 47),
    "snow": (5, 7, 13, 14, 15, 16, 41, 42, 43, 46),
    "rain": (6, 8, 9, 10, 11, 12, 17, 18, 35, 40),
    "fog": (19, 20, 21, 22),
    "wind": (23, 24),
    "cloud": (25, 26),
    "partly-night": (27, 29),
    "partly": (28, 30, 44),
    "moon": (31, 33),
    "sun": (32, 34, 36),
}
ICON_FOR_CODE = {code: icon for icon, codes in ICON_CODES.items() for code in codes}


def icon():
    """The texture for the current conditions, or "" if the weather isn't known."""
    if not xbmc.getCondVisibility("Weather.IsFetched"):
        return ""
    code = xbmc.getInfoLabel("Weather.FanartCode").strip()
    if not code.isdigit():
        # Some add-ons give the code only as their icon's file name, such as ".../28.png".
        icon_name = os.path.basename(xbmc.getInfoLabel("Weather.ConditionsIcon"))
        code = os.path.splitext(icon_name)[0]
    name = ICON_FOR_CODE.get(int(code)) if code.isdigit() else None
    return f"jellyelec-weather-{name}.png" if name else ""

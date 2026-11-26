# JellyELEC artwork

Created by fattykidd with Google Gemini, then upscaled with
[Upscayl](https://github.com/upscayl/upscayl) (Digital Art model). Kept here at 2560×1440.

| File | What it is | Used for |
|---|---|---|
| `ocean.png` | Deep water with light rays and drifting particles | The splash background |
| `triangle.png` | The glowing circuit triangle, on black | The splash, behind the jellyfish |
| `jellyfish.png` | The jellyfish, on black, lined up with the triangle | The splash, in front |
| `ocean-jellyfish.png` | The ocean with jellyfish drifting through it | Not used yet: a loading screen or screensaver later |

`tools/make_splash.py` builds the add-on's splash pictures from these. The pictures on black
become see-through layers, their brightness used as transparency, so the glow blends over the
ocean. To change the splash, replace a file here (same size and layout) and run the script.

"""Build an installable Kodi zip of the add-on.

Run from anywhere:  python tools/build.py
The zip is written to dist/script.jellyelec-<version>.zip
"""

import pathlib
import xml.etree.ElementTree as ElementTree
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADDON_DIR = ROOT / "script.jellyelec"
DIST_DIR = ROOT / "dist"
SKIPPED_DIRS = {"__pycache__"}
SKIPPED_SUFFIXES = {".pyc", ".pyo"}


def addon_version():
    return ElementTree.parse(ADDON_DIR / "addon.xml").getroot().get("version")


def should_include(path):
    return (
        path.is_file()
        and path.suffix not in SKIPPED_SUFFIXES
        and not SKIPPED_DIRS.intersection(path.parts)
    )


def main():
    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / f"{ADDON_DIR.name}-{addon_version()}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            if should_include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Built {target}")


if __name__ == "__main__":
    main()

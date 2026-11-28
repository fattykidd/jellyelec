#!/usr/bin/env bash
#
# Build JellyELEC from a p3i (CoreELEC) release: an image to flash, and an update tar that
# updates a box already running JellyELEC without reflashing.
#
# Usage:   sudo bash image/remaster.sh
#              Builds on the p3i release in image/p3i-base.json. Its flash image and update
#              tar are downloaded into image/downloads/ (once) and checked against the file's
#              SHA-256 checksums.
#          sudo bash image/remaster.sh path/to/Flash_...img.gz [path/to/Update_...tar]
#              Builds on files you already have. Without an update tar, only the image is made.
#
# Result, in dist/ (<build> is the build's date and time in UTC, such as 202611271830):
#   JellyELEC-<build>-p3i-<release>-AM6B.img.gz   the image to flash
#   JellyELEC-<build>-p3i-<release>.tar           the update: copy it into the box's Update
#                                                 folder and restart, or install it from
#                                                 JellyELEC's Settings once it's released
#   JellyELEC-<build>-p3i-<release>.json          what the build contains (also inside it)
#   *.sha256                                      checksums of the image and the tar
#
# What it changes (everything else is pannal's p3i image, untouched):
#   SYSTEM (the read-only system)
#     - adds the JellyELEC add-on as a built-in add-on that's always enabled
#     - adds the files in image/overlay/: first-boot settings and the update block
#     - replaces the skins' startup screen with script.jellyelec/resources/skin_patch/Startup.xml (no Kodi home screen at boot),
#       and their full-screen video window, OSD and seek bar with JellyELEC's (VideoFullScreen.xml,
#       VideoOSD.xml, DialogSeekBar.xml, and the textures they use)
#     - adds JellyELEC's fonts (script.jellyelec/resources/skin_patch/fonts/) to the skins, defined in each Font.xml
#     - uses JellyELEC's splash for Kodi's splash screen, and turns that screen on
#     - for new installs: names Kodi JellyELEC, turns off automatic add-on updates, and
#       allows installing add-ons from zip files
#   COREELEC (the boot partition)
#     - dtb.img for the Ugoos AM6B+, the Ugoos remote's remote.conf, and the HDMI-CEC name
#     - oemsplash.png: JellyELEC's splash in place of p3i's during the early boot
#     - Wake-on-LAN turned on
#   dovi.ko is NOT included: it's added by hand after flashing (see the README).
# The update tar is p3i's own update tar with JellyELEC's SYSTEM in it; everything else in it
# (the kernel, device trees) is p3i's. Boxes keep their COREELEC partition settings.
#
# Needs root, so the system files keep their owners when unpacked and repacked.
# Needs: gzip, python3, mtools, squashfs-tools, tar.

set -euo pipefail

IMAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$IMAGE_DIR")"
BASE_FILE="$IMAGE_DIR/p3i-base.json"
DOWNLOAD_DIR="$IMAGE_DIR/downloads"
ADDON_DIR="$REPO_DIR/script.jellyelec"
DIST_DIR="$REPO_DIR/dist"

ADDON_ID="script.jellyelec"
SPLASH="$ADDON_DIR/resources/skins/Default/media/jellyelec-splash.png"
DEVICE_TREE="g12b_s922x_ugoos_am6b.dtb"
DEVICE_NAME="AM6B"
BOX_NAME="JellyELEC"
SKINS=(skin.p3i.estuary skin.estuary)
SECTOR_SIZE=512

# How p3i packs SYSTEM (from "unsquashfs -s"); the repacked one must match.
SQUASHFS_OPTIONS=(-comp lzo -Xalgorithm lzo1x_999 -Xcompression-level 9 -b 524288 -no-xattrs -noappend)

# Helpers ----------------------------------------------------------------------------

step() { echo; echo "== $*"; }
fail() { echo "Error: $*" >&2; exit 1; }

partition_location() {
    # Prints "start size" (in sectors) of an MBR partition, numbered from 1.
    python3 - "$1" "$2" <<'PYTHON'
import struct, sys
path, number = sys.argv[1], int(sys.argv[2])
with open(path, "rb") as image:
    mbr = image.read(512)
entry = mbr[446 + (number - 1) * 16 : 462 + (number - 1) * 16]
start, size = struct.unpack("<II", entry[8:16])
print(start, size)
PYTHON
}

# Checks -----------------------------------------------------------------------------

[ "$(id -u)" -eq 0 ] || fail "run this with sudo, so system files keep their owners."
for tool in gzip python3 mdir mcopy mdel unsquashfs mksquashfs md5sum sha256sum tar; do
    command -v "$tool" >/dev/null || fail "missing tool: $tool (install mtools and squashfs-tools)"
done

# Which p3i files to build on: the ones named on the command line, or the base file's.
if [ $# -ge 1 ]; then
    IMAGE_GZ="$1"
    UPDATE_TAR="${2:-}"
    BASE_RELEASE=""
    DOVI_MODULE="dovi.ko"
else
    step "Getting p3i's files"
    mapfile -t base_files < <(python3 "$REPO_DIR/tools/p3i_base.py" fetch "$DOWNLOAD_DIR")
    [ "${#base_files[@]}" -eq 2 ] || fail "couldn't get p3i's files (see above)."
    IMAGE_GZ="${base_files[0]}"
    UPDATE_TAR="${base_files[1]}"
    BASE_RELEASE="$(python3 -c "import json; print(json.load(open('$BASE_FILE'))['release'])")"
    DOVI_MODULE="$(python3 -c "import json; print(json.load(open('$BASE_FILE')).get('dovi_module', 'dovi.ko'))")"
    if [ -n "${SUDO_USER:-}" ]; then
        chown -R "$SUDO_USER": "$DOWNLOAD_DIR"
    fi
fi
[ -f "$IMAGE_GZ" ] || fail "no such file: $IMAGE_GZ"
[ -z "$UPDATE_TAR" ] || [ -f "$UPDATE_TAR" ] || fail "no such file: $UPDATE_TAR"

ADDON_VERSION="$(python3 -c "import xml.etree.ElementTree as e; print(e.parse('$ADDON_DIR/addon.xml').getroot().get('version'))")"
BUILD_ID="$(date -u +%Y%m%d%H%M)"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Unpack -----------------------------------------------------------------------------

step "Unpacking $(basename "$IMAGE_GZ")"
gzip -dc "$IMAGE_GZ" > "$work/image.img"

read -r boot_start boot_size < <(partition_location "$work/image.img" 1)
dd if="$work/image.img" of="$work/boot.img" bs="$SECTOR_SIZE" skip="$boot_start" count="$boot_size" status=none
mcopy -n -i "$work/boot.img" ::SYSTEM "$work/SYSTEM"
unsquashfs -no-progress -d "$work/system" "$work/SYSTEM" > /dev/null

P3I_RELEASE="$(sed -n 's/^VERSION=".*_p3i_\([^_]*\)_.*"$/\1/p' "$work/system/etc/os-release")"
[ -n "$P3I_RELEASE" ] || fail "this doesn't look like a p3i image (no p3i version in /etc/os-release)."
[ -z "$BASE_RELEASE" ] || [ "$P3I_RELEASE" = "$BASE_RELEASE" ] \
    || fail "the image is p3i $P3I_RELEASE, but p3i-base.json says $BASE_RELEASE."
# p3i's own SYSTEM, to check the update tar holds the same one.
p3i_system_md5="$(md5sum "$work/SYSTEM" | cut -d' ' -f1)"
NAME="JellyELEC-$BUILD_ID-p3i-$P3I_RELEASE"
echo "p3i $P3I_RELEASE, JellyELEC $ADDON_VERSION, build $BUILD_ID"

# SYSTEM changes ---------------------------------------------------------------------

step "Adding JellyELEC $ADDON_VERSION as a built-in add-on"
rm -rf "$work/system/usr/share/kodi/addons/$ADDON_ID"
cp -r "$ADDON_DIR" "$work/system/usr/share/kodi/addons/$ADDON_ID"
find "$work/system/usr/share/kodi/addons/$ADDON_ID" \( -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
manifest="$work/system/usr/share/kodi/system/addon-manifest.xml"
grep -q "<addon>$ADDON_ID</addon>" "$manifest" \
    || sed -i "s|</addons>|  <addon>$ADDON_ID</addon>\n</addons>|" "$manifest"

step "Adding the overlay files"
cp -r "$IMAGE_DIR/overlay/." "$work/system/"

# Files copied from this repo belong to whoever cloned it; in the system they're root's.
chown -R root:root "$work/system/usr/share/kodi/addons/$ADDON_ID" "$work/system/usr/share/jellyelec" \
    "$work/system/usr/lib/tmpfiles.d/jellyelec.conf"

step "Replacing the skins' startup screen and player screens"
# The same files skin_patch.py keeps in a skin installed into /storage: Startup.xml (no Kodi
# home screen at boot), and the full-screen video window, OSD and seek bar, with their textures.
skin_media="$ADDON_DIR/resources/skins/Default/media"
for skin in "${SKINS[@]}"; do
    skin_dir="$work/system/usr/share/kodi/addons/$skin"
    [ -d "$skin_dir/xml" ] || continue
    for window in Startup.xml VideoFullScreen.xml VideoOSD.xml DialogSeekBar.xml Custom_1109_TopBarOverlay.xml; do
        install -o root -g root -m 0644 "$ADDON_DIR/resources/skin_patch/$window" "$skin_dir/xml/$window"
    done
    mkdir -p "$skin_dir/media"
    install -o root -g root -m 0644 "$skin_media"/jellyelec-osd-*.png "$skin_media/jellyelec-pill.png" \
        "$skin_media/jellyelec-white.png" "$skin_media/jellyelec-fade-bottom.png" \
        "$skin_media/jellyelec-badge-filled.png" "$skin_dir/media/"
    echo "  $skin"
done

step "Adding JellyELEC's fonts to the skins"
# The font files go into each skin's fonts folder, and their definitions into every
# fontset in its Font.xml, so JellyELEC's screens can use them by name.
for skin in "${SKINS[@]}"; do
    skin_dir="$work/system/usr/share/kodi/addons/$skin"
    [ -f "$skin_dir/xml/Font.xml" ] || continue
    install -o root -g root -m 0644 "$ADDON_DIR"/resources/skin_patch/fonts/*.otf "$ADDON_DIR"/resources/skin_patch/fonts/*.ttf "$skin_dir/fonts/"
    python3 - "$skin_dir/xml/Font.xml" "$ADDON_DIR/resources/skin_patch/jellyelec-fonts.xml" <<'PYTHON'
import re, sys
font_xml, fragment = sys.argv[1], sys.argv[2]
with open(fragment, encoding="utf-8") as file:
    fonts = re.sub(r"<!--.*?-->", "", file.read(), flags=re.S).strip()
with open(font_xml, encoding="utf-8") as file:
    text = file.read()
if "<name>JE_Title</name>" not in text:
    text = text.replace("</fontset>", f"{fonts}\n</fontset>")
    with open(font_xml, "w", encoding="utf-8") as file:
        file.write(text)
PYTHON
    echo "  $skin"
done

step "Using JellyELEC's splash for Kodi's splash screen"
install -o root -g root -m 0644 "$SPLASH" "$work/system/usr/share/kodi/media/splash.png"
sed -i 's|<splash>false</splash>|<splash>true</splash>|' "$work/system/usr/share/kodi/system/advancedsettings.xml"

step "Kodi settings for new installs"
# Kodi copies this file into place the first time it starts, and never again.
guisettings="$work/system/usr/share/kodi/config/guisettings.xml"
add_kodi_setting() {
    grep -q "id=\"$1\"" "$guisettings" \
        || sed -i "s|</settings>|  <setting id=\"$1\">$2</setting>\n</settings>|" "$guisettings"
}
# The name other devices see for this box's Kodi services.
add_kodi_setting services.devicename "$BOX_NAME"
# No automatic add-on updates: a skin update from p3i's repository would undo the
# JellyELEC startup screen, and an appliance shouldn't change itself mid-use.
# (0 = install automatically, 1 = notify only, 2 = never check)
add_kodi_setting general.addonupdates 2
# Allow installing add-ons from zip files, such as a new JellyELEC test build.
add_kodi_setting addons.unknownsources true

step "Recording what this build contains"
# JellyELEC reads this to know which build a box runs, and the release carries a copy so a
# box can see what an update needs before installing it.
python3 - "$work/build.json" "$BUILD_ID" "$P3I_RELEASE" "$ADDON_VERSION" "$DOVI_MODULE" <<'PYTHON'
import json, sys
path, build, release, addon_version, dovi_module = sys.argv[1:]
with open(path, "w", encoding="utf-8") as file:
    json.dump({"build": build, "p3i_release": release, "addon_version": addon_version,
               "dovi_module": dovi_module}, file, indent=2)
    file.write("\n")
PYTHON
install -o root -g root -m 0644 "$work/build.json" "$work/system/usr/share/jellyelec/build.json"
cat "$work/build.json"

step "Packing SYSTEM"
rm -f "$work/SYSTEM"
mksquashfs "$work/system" "$work/SYSTEM" "${SQUASHFS_OPTIONS[@]}" -quiet
system_md5="$(md5sum "$work/SYSTEM" | cut -d' ' -f1)"
echo "$system_md5  target/SYSTEM" > "$work/SYSTEM.md5"

# COREELEC partition changes ---------------------------------------------------------

step "Updating the COREELEC partition"
mcopy -o -i "$work/boot.img" "$work/SYSTEM" ::SYSTEM
mcopy -o -i "$work/boot.img" "$work/SYSTEM.md5" ::SYSTEM.md5

# The device tree for the box, which p3i leaves to be copied by hand.
mcopy -n -i "$work/boot.img" "::device_trees/$DEVICE_TREE" "$work/dtb.img"
mcopy -o -i "$work/boot.img" "$work/dtb.img" ::dtb.img

# JellyELEC's splash in place of p3i's during the early boot, before Kodi starts.
mcopy -o -i "$work/boot.img" "$SPLASH" ::oemsplash.png

# The Ugoos remote's key map, so the remote in the box works straight away.
mcopy -o -i "$work/boot.img" "$IMAGE_DIR/boot/remote.conf" ::remote.conf

# Boot settings: the name the TV shows for this input over HDMI-CEC, and Wake-on-LAN on,
# so the box can be woken from standby over the network.
mcopy -n -i "$work/boot.img" ::config.ini "$work/config.ini"
sed -i -e "s|^# cec_osd_name=.*|cec_osd_name='$BOX_NAME'|" -e "s|^# wol=.*|wol='1'|" "$work/config.ini"
mcopy -o -i "$work/boot.img" "$work/config.ini" ::config.ini

dd if="$work/boot.img" of="$work/image.img" bs="$SECTOR_SIZE" seek="$boot_start" conv=notrunc status=none

# Pack -------------------------------------------------------------------------------

step "Compressing the image"
mkdir -p "$DIST_DIR"
outputs=()
image_output="$DIST_DIR/$NAME-$DEVICE_NAME.img.gz"
gzip -c "$work/image.img" > "$image_output"
outputs+=("$image_output")
rm -f "$work/image.img" "$work/boot.img"

if [ -n "$UPDATE_TAR" ]; then
    step "Making the update tar from $(basename "$UPDATE_TAR")"
    # p3i's update tar holds one folder, with the kernel and SYSTEM under target/.
    mkdir "$work/update"
    tar -xf "$UPDATE_TAR" -C "$work/update"
    folders=("$work"/update/*/)
    [ "${#folders[@]}" -eq 1 ] && [ -f "${folders[0]}target/SYSTEM" ] \
        || fail "$(basename "$UPDATE_TAR") isn't laid out like a CoreELEC update tar."
    update_dir="${folders[0]%/}"
    # It must be the same p3i build as the image, so its kernel matches our SYSTEM's modules.
    [ "$(cut -d' ' -f1 "$update_dir/target/SYSTEM.md5")" = "$p3i_system_md5" ] \
        || fail "$(basename "$UPDATE_TAR") isn't the same p3i build as $(basename "$IMAGE_GZ")."
    cp "$work/SYSTEM" "$update_dir/target/SYSTEM"
    cp "$work/SYSTEM.md5" "$update_dir/target/SYSTEM.md5"
    if [ -f "$update_dir/target/SYSTEM.sha256" ]; then
        echo "$(sha256sum "$work/SYSTEM" | cut -d' ' -f1)  target/SYSTEM" > "$update_dir/target/SYSTEM.sha256"
    fi
    mv "$update_dir" "$work/update/$NAME"
    tar_output="$DIST_DIR/$NAME.tar"
    tar -cf "$tar_output" -C "$work/update" "$NAME"
    outputs+=("$tar_output")
fi

step "Writing checksums"
cp "$work/build.json" "$DIST_DIR/$NAME.json"
for file in "${outputs[@]}"; do
    (cd "$DIST_DIR" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256")
done

if [ -n "${SUDO_USER:-}" ]; then
    chown -R "$SUDO_USER": "$DIST_DIR"
fi
echo
echo "Done:"
for file in "${outputs[@]}" "$DIST_DIR/$NAME.json"; do
    echo "  $file"
done

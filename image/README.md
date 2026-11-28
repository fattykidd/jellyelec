# JellyELEC images

JellyELEC images are built from pannal's [p3i](https://github.com/pannal/CoreELEC) CoreELEC
releases. `remaster.sh` unpacks a p3i image, adds JellyELEC and a handful of settings, and packs
it back up. Everything else is p3i exactly as released. Each build comes as an image to flash
and as an update tar, which updates a box already running JellyELEC without reflashing.

## Building an image

Needs Linux with `mtools` and `squashfs-tools`:

- Fedora/RHEL: `sudo dnf install mtools squashfs-tools`
- Ubuntu/Debian: `sudo apt install mtools squashfs-tools`

From the repo folder, run:

```
sudo bash image/remaster.sh
```

It builds on the p3i release recorded in `p3i-base.json`. The first time, it downloads that
release's flash image and update tar into `image/downloads/` (about 500 MB, kept for next
time) and checks them against the SHA-256 checksums in the file. It needs `sudo` so the system
files keep their owners when they're unpacked and packed again.

The results go in `dist/`, named for the build (its date and time in UTC) and p3i release:

| File | What it's for |
|---|---|
| `JellyELEC-<build>-p3i-<release>-AM6B.img.gz` | A new box: flash it like any CoreELEC image. |
| `JellyELEC-<build>-p3i-<release>.tar` | A box already running JellyELEC: the update. |
| `JellyELEC-<build>-p3i-<release>.json` | What the build contains (also inside it, as `/usr/share/jellyelec/build.json`). |
| `*.sha256` | Checksums of the image and the tar. |

To build on p3i files you already have instead:
`sudo bash image/remaster.sh <Flash_...img.gz> [<Update_...tar>]`.

## Updating a box without reflashing

The update tar is p3i's own update tar with JellyELEC's system in it, so it installs the same
way p3i's and CoreELEC's updates do. Settings, sign-in, the COREELEC partition (dovi.ko,
config.ini) and everything in `/storage` are kept.

- **From JellyELEC:** Settings › Check for updates offers the newest published image release
  (see below), downloads its tar, and restarts to install it.
- **By hand:** copy the `.tar` into the box's **Update** folder (the `Update` share over Samba,
  or `/storage/.update` over SSH) and restart. CoreELEC installs it while the box starts.

p3i asks for one more step after an in-place update (from T5 on): Kodi's CoreELEC settings
(Settings › System › CoreELEC) must be reset to their defaults, followed by a restart.
JellyELEC does this by itself on the first start after an update to a different p3i release:
it resets those settings, sets video processor mode's Dolby Vision settings to be made again,
and restarts once. A freshly flashed box skips it.

If an update's p3i needs a different Dolby Vision module (the `.json`'s `dovi_module`),
JellyELEC says so before downloading. Copy the new module onto the COREELEC drive before
restarting, or Dolby Vision titles play in HDR10 until it's there.

## Keeping up with p3i

`p3i-base.json` records the p3i release JellyELEC is built on: its tag, the flash image and
update tar with their checksums, and the Dolby Vision module it needs. Two GitHub workflows
(in `.github/workflows/`) look after it:

- **Watch p3i for new releases** runs every day. When pannal publishes a new p3i release, it
  opens a pull request that moves `p3i-base.json` to it, with pannal's release notes and a
  checklist, and builds JellyELEC on it. The test build (image and tar) is linked in the pull
  request; if the build fails, the pull request says so. `tools/p3i_base.py` does the looking.
- **Publish an image release** is run by hand from the Actions tab, once a build has been
  tested on a box. It builds JellyELEC on the base and publishes it as an image release
  (tagged `image-<build>`), which boxes find under Check for updates.

Both need, in the repository's Settings › Actions › General › Workflow permissions: **Read and
write permissions**, and **Allow GitHub Actions to create and approve pull requests**.

A new p3i release usually means checking one thing by hand: whether it needs a new Dolby Vision
module. pannal's release notes say so. If it does, change `dovi_module` in `p3i-base.json` on
the pull request's branch before merging.

## What JellyELEC changes

In the system (read-only) part:

- JellyELEC is added as a built-in add-on that's always enabled.
- `overlay/` is copied over the system as-is:
  - `usr/lib/tmpfiles.d/jellyelec.conf`: first-boot setup. It skips CoreELEC's first-run
    wizard (JellyELEC's setup replaces it) and turns off p3i's built-in updater, which would
    otherwise replace JellyELEC with stock p3i.
  - `usr/share/jellyelec/oe_settings.xml`: CoreELEC's settings for a new box, with the
    wizard marked done. (JellyELEC's setup names the box JellyELEC on the network.)
- `script.jellyelec/resources/skin_patch/Startup.xml` replaces the skins' startup screen, so the boot goes from the splash
  straight into JellyELEC without showing Kodi's home screen.
- JellyELEC's fonts (Inter and Outfit, from `script.jellyelec/resources/skin_patch/fonts/`) are added to the skins, with
  their definitions from `skin_patch/jellyelec-fonts.xml` added to each skin's `Font.xml`.
  JellyELEC's screens use them by name; without them (an older image), Kodi's default font
  is used instead.
- JellyELEC's still splash (from the add-on, `resources/skins/Default/media/jellyelec-splash.png`)
  becomes Kodi's splash screen, which is turned on. Once Kodi is up, the startup screen and
  JellyELEC's backdrop take over from it, animated. The pictures are built by
  `tools/make_splash.py` from the artwork in `artwork/`.
- New installs name Kodi JellyELEC and don't update add-ons automatically: a skin update
  from p3i's add-on repository would undo the startup screen. They also allow installing
  add-ons from zip files ("unknown sources"), for JellyELEC test builds.

On the COREELEC (boot) partition:

- `dtb.img` is set to the Ugoos AM6B+ device tree.
- `boot/remote.conf` is added, so the Ugoos remote works straight away.
- `oemsplash.png` (the same JellyELEC splash) replaces p3i's splash during the early boot.
- The HDMI-CEC name (what the TV shows for this input) is set to JellyELEC.
- Wake-on-LAN is turned on (`wol='1'` in `config.ini`, matched in CoreELEC's settings).

## Dolby Vision: adding dovi.ko

The Dolby Vision module can't be included in the image, so it's added by hand once, after
flashing. Its name is `dovi_module` in `p3i-base.json`: `dovi.ko` for p3i T4 and T5. It could
change with a later p3i release.

p3i T5 can also load a second, newer Dolby library, `dovi5.ko`, from avdvplus R10. It's
optional, sits alongside `dovi.ko` (which is still needed), and goes in `/storage/.config/`
rather than on the COREELEC drive. See pannal's T5 release notes.

1. Put the freshly flashed card or USB stick in a computer.
2. Open the drive named **COREELEC**.
3. Copy `dovi.ko` into it: the top folder, next to `kernel.img`, not into a subfolder.
4. Eject it, put it back in the box, and turn it on.

This works the same on Linux, macOS and Windows. JellyELEC's setup checks for the file and
explains these steps if it's missing.

## Looking inside an image

`inspect.sh` reports what's in a p3i image (partition layout, how SYSTEM is packed, and the
files JellyELEC changes) without changing anything. It was used to plan `remaster.sh`, and
is worth re-running on each new p3i release to check nothing has moved.

## Credits

JellyELEC images are p3i by pannal and the p3i contributors, based on U3k by Jamal and the
CoreELEC, LibreELEC and Kodi projects. Their code is GPLv2 and owned by its authors.
`boot/remote.conf` is the standard key map for the Ugoos UR-01 remote. The splash artwork was
created by fattykidd with Google Gemini and upscaled with Upscayl (see `artwork/README.md`).
The fonts are Inter by The Inter Project Authors and Outfit by The Outfit Project Authors,
both under the SIL Open Font License 1.1 (licences in `script.jellyelec/resources/skin_patch/fonts/`).

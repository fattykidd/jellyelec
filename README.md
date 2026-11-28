# JellyELEC

A Jellyfin-first appliance for CoreELEC, in the spirit of RasPlex. JellyELEC boots straight
into its own full-screen interface and uses Kodi only as the playback engine, so Dolby Vision
(including FEL), HDR and audio passthrough play exactly as they do in CoreELEC.

It's built for the Ugoos AM6B+ on pannal's [p3i](https://github.com/pannal/CoreELEC) CoreELEC
builds, and ships both as a Kodi add-on (`script.jellyelec`) and as a complete image.

**Status:** in active development and used daily on one home theatre. Expect changes.

## What it does

### Home
- A library bar across the top, with a pill for each Jellyfin library sized to its name. It
  slides along as you move, and wraps around through the Settings button.
- A spotlight for whatever is focused: fanart, clear logo, year, rating, runtime, **Ends at**,
  resolution and audio badges, and the plot.
- Rows for each library: Continue Watching, Next Up (TV) and Recently Added as landscape cards,
  and a Random row of posters.
- Weather (Open-Meteo) and a clock that follows the regional 12- or 24-hour setting.

### Library grid
- Every movie or show in a library, A to Z, with the same details as the home spotlight.
- Movie collections can be shown once in place of their movies, with artwork borrowed from a
  movie in the collection when Jellyfin has none.

### Detail page
- Fanart, clear logo, Ends at, resolution and audio badges, studio and genre chips, the
  directors, and the plot.
- Pill buttons: Resume or Play, From start, Trailer, Version (for titles with several files),
  **Media info**, **Artwork**, and Watched and Favourite toggles that save to Jellyfin.
- Rows: Seasons, Cast and crew (round headshots), More like this, and Special features.
- Selecting a studio, genre, director or cast member opens every title in your libraries that
  shares it, as in Jellyfin's web app.
- **Media info** shows the file and every video, audio and subtitle track, including the Dolby
  Vision profile. **Artwork** browses every poster, backdrop, logo and disc Jellyfin has.

### Player
- Direct play only: the original file, streamed from the server with no transcoding. Progress,
  pauses and stops are reported to Jellyfin.
- JellyELEC's own OSD and seek bar: clear logo, badges, progress, chapter name and Ends at, with
  buttons for Chapters, back 10 seconds, Play/Pause, forward 30 seconds, Audio, Subtitles,
  Player info (Kodi's player process info) and Stop.
- Audio and subtitle pickers that use Jellyfin's track names. Back during playback opens the
  chapter list.

### Live TV
- Channel list with what's on now and next, from Jellyfin's Live TV.
- While a channel plays, the list becomes the guide, with the live picture in a corner.
- Channel up and down, a guide key, and a watchdog that reconnects a stalled channel.

### Setup and Settings
- **Quick setup:** Dolby Vision, how the box is connected (TV, AV receiver, or receiver and video
  processor), then finding the server on the network and signing in, by Quick Connect code or
  username and password.
- **Custom setup** adds Wi-Fi, the box's name, time zone, SSH, file sharing, Bluetooth and weather.
- Sound and picture are set for the connection: audio passthrough, Dolby Vision mode, LLDV for
  video processors, and p3i's "DV Output Signal Type for Video Processor" (HDR10 4:2:2 12-bit).
- **Settings** covers all of that, plus movie collections, how media details show (badges or
  text), Live TV guide options, remote control from other devices (for the Unfolded Circle Kodi
  integration), regional settings, updates, power, and Exit to Kodi.

### Appliance
- Opens when the box starts and reopens if it ever closes. JellyELEC's splash covers every gap,
  so Kodi's own home screen is never seen.
- The box's name is kept across system updates, including on the network (Samba).
- **Check for updates** installs new add-on releases, and downloads system updates (new p3i
  bases) to install at the next restart, with no reflashing.

## Repository

| Folder | What's in it |
|---|---|
| `script.jellyelec/` | The Kodi add-on. |
| `script.jellyelec/resources/skin_patch/` | Files JellyELEC puts into the Kodi skin: the startup screen, the OSD and seek bar, and fonts. |
| `image/` | Builds JellyELEC images and update tars from p3i releases. See [image/README.md](image/README.md). |
| `tools/` | `build.py` (the add-on zip), `release.sh` (publish a release), `make_textures.py` (the interface's shapes and icons), `p3i_base.py` (track p3i releases). |
| `.github/workflows/` | `watch-p3i.yml` opens a pull request when pannal publishes a new p3i release; `publish-image.yml` builds and publishes an image. |

## Building and releasing

- **Add-on zip:** `python3 tools/build.py` writes `dist/script.jellyelec-<version>.zip`. Install it
  on a box with Kodi's "Install from zip file".
- **Release:** bump the version in `script.jellyelec/addon.xml`, commit and push, then run
  `bash tools/release.sh`. Boxes pick it up through Settings > Check for updates.
- **Image:** see [image/README.md](image/README.md).

## Credits

- [Jellyfin](https://jellyfin.org), the media server JellyELEC is a client for.
- [Kodi](https://kodi.tv) and [CoreELEC](https://coreelec.org), which do the playing.
- pannal's [p3i](https://github.com/pannal/CoreELEC) CoreELEC builds, which JellyELEC images are
  built on.
- [Inter](https://rsms.me/inter/) and [Outfit](https://github.com/Outfitio/Outfit-Fonts), under
  the SIL Open Font License (licences in `script.jellyelec/resources/skin_patch/fonts/`).
- Weather from [Open-Meteo](https://open-meteo.com) through Kodi's Open-Meteo weather add-on.

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).

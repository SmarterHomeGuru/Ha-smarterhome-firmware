# SmarterHome Firmware for Home Assistant

See when your smart home devices have new firmware, what changed in plain English, and whether
other owners had problems with it. Data comes from the [SmarterHome.guru firmware tracker](https://www.smarterhome.guru/firmware),
which checks each maker's official release notes.

SmarterHome Firmware adds a **firmware update entity** to each device that Home Assistant already
knows and the tracker covers. It shows up in **Settings → Updates** and on the device page, with
release notes, owner reports ("worked fine" / "had problems") and a link to the version history.

It **never installs anything**. Update with the maker's app or the device's own integration, as usual.

## What it covers

Devices whose integration reports a firmware version and whose maker the tracker follows, including:

- Shelly (Gen1 and Gen2+), Reolink cameras, TP-Link Kasa and Tapo, Philips Hue bridges
- Aqara, IKEA and other Zigbee devices through ZHA or Zigbee2MQTT, where the tracker lists the model
- ESPHome, Zigbee2MQTT, Tasmota, WLED, Frigate, deCONZ, Music Assistant, Home Assistant OS
- Sonos (latest version shown; Sonos numbers its versions differently in Home Assistant, so no "update available" flag)

Cloud-only devices (Ring, Blink, Wyze, most Wi-Fi plugs) usually don't report a version to Home
Assistant, so they're not covered. **Settings → Devices & services → SmarterHome Firmware → ⋮ →
Download diagnostics** lists which of your devices matched and which didn't.

When the version your device reports can't be lined up with the maker's numbering, the entity
shows the latest version but does not claim an update is available. A wrong alert is worse than none.

## Privacy

Every 6 hours the integration downloads one public file,
`https://www.smarterhome.guru/api/firmware-catalog.json`. It is the same file for everyone.
Matching your devices happens on your Home Assistant. Nothing about your devices, your home or
you is sent. The site sets no cookies on that request and sees only an IP address and the
integration's version.

## Install

With [HACS](https://hacs.xyz): HACS → ⋮ → Custom repositories → add
`https://github.com/rdiamondbww/ha-smarterhome-firmware` (type Integration) → install
**SmarterHome Firmware** → restart Home Assistant → Settings → Devices & services → Add
integration → SmarterHome Firmware.

Manual: copy `custom_components/smarterhome_firmware` into your `config/custom_components/` and restart.

### Options

- **Skip devices whose own integration already offers firmware updates** (on by default), so
  ESPHome, Shelly or Zigbee2MQTT devices don't get two update entities. Turn it off to see our
  notes and owner reports next to theirs.
- **Include beta and preview releases** (off by default).

## Phone notifications

Import the blueprint:

[![Open your Home Assistant instance and show the blueprint import dialog.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frdiamondbww%2Fha-smarterhome-firmware%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fsmarterhome_firmware%2Fnotify_new_firmware.yaml)

Pick the firmware entities to watch and your phone. You get "Hue Bridge v2 6.5.1978688000 is
out. 2 owners reported problems. Read before updating." Tap it to open the release notes. You can
limit it to releases with reported problems.

## Missing a device?

Open an issue with the manufacturer and model from the diagnostics file. Brands are added to the
tracker over time.

"""Matching realistic Home Assistant device records against the real catalog (fixture from Nov 26, 2026)."""

import json
from pathlib import Path

import pytest

from custom_components.smarterhome_firmware.matcher import HaDevice, Matcher

CATALOG = json.loads((Path(__file__).parent / "fixtures" / "catalog.json").read_text())


@pytest.fixture(scope="module")
def matcher():
    return Matcher(CATALOG)


def dev(manufacturer, model, model_id=None, sw="1.0", domains=("x",)):
    return HaDevice(id="d1", manufacturer=manufacturer, model=model, model_id=model_id, sw_version=sw, domains=list(domains))


@pytest.mark.parametrize(
    ("device", "key", "method"),
    [
        (dev("Shelly", "Shelly 1", "SHSW-1", domains=["shelly"]), "shelly/shelly-1-shsw-1", "model"),
        (dev("Shelly", "Shelly Plus 1PM", "SNSW-001P16EU", domains=["shelly"]), "shelly/all-shelly-gen2-devices", "fallback"),
        (dev("Signify Netherlands B.V.", "Philips hue", "BSB002", domains=["hue"]), "philips-hue/hue-bridge-v2", "model"),
        (dev("Espressif", "esp32dev", domains=["esphome"]), "esphome/esphome", "domain"),
        (dev("Zigbee2MQTT", "Bridge", domains=["mqtt"]), "zigbee2mqtt/zigbee2mqtt", "rule"),
        (dev("Home Assistant", "Home Assistant Operating System", domains=["hassio"]), "home-assistant/home-assistant-os", "rule"),
        (dev("LUMI", "lumi.motion.ac02", domains=["zha"]), "aqara/motion-sensor-p1-rtcgq14lm", "model"),
        (dev("Aqara", "Motion sensor P1", "RTCGQ14LM", domains=["mqtt"]), "aqara/motion-sensor-p1-rtcgq14lm", "model"),
        (dev("TP-Link", "C310", domains=["tplink"]), "tp-link-tapo/tapo-c310", "model"),
        (dev("Reolink", "P330", domains=["reolink"]), "reolink/p330", "model"),
        (dev("Sonos", "Era 100", "S39", domains=["sonos"]), None, "model"),
        (dev("Sonos", "Five", "S29", domains=["sonos"]), "sonos/all-sonos-s2-speakers", "fallback"),
    ],
)
def test_matches(matcher, device, key, method):
    m = matcher.match(device)
    assert m is not None, device
    assert m.method == method
    if key is not None:
        assert m.key == key
    else:
        assert m.key.startswith("sonos/sonos-arc-ultra")


@pytest.mark.parametrize(
    "device",
    [
        dev("Shelly", "Shelly 9", "SHXX-9", domains=["shelly"]),  # unknown Gen1: never the Gen2 train
        dev("Signify Netherlands B.V.", "Hue color lamp", "LCT015", domains=["hue"]),  # Hue lights: no per-model data
        dev("Acme Corp", "Widget", domains=["acme"]),
        dev("Shelly", "Shelly 1", "SHSW-1", sw=None, domains=["shelly"]),
    ],
)
def test_no_match(matcher, device):
    assert matcher.match(device) is None


def test_every_entry_has_a_stable_release():
    for e in CATALOG["devices"]:
        assert e["stable"]["version"], e["key"]

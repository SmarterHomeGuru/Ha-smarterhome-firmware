"""Version comparison across makers' formats."""

import pytest

from custom_components.smarterhome_firmware.versions import compare, installed_from_sw_version


@pytest.mark.parametrize(
    ("latest", "installed", "expected"),
    [
        ("2.2.1", "1.4.4", 1),  # Shelly Gen2
        ("v1.14.0-gcb84623", "20230913-112003/v1.14.0-gcb84623", 0),  # Shelly Gen1 as HA reports it
        ("v1.14.0-gcb84623", "20230118-111316/v1.12.2-gcb84623", 1),
        ("2026.11.1", "2026.10.2", 1),  # ESPHome
        ("2026.11.1", "2026.11.1", 0),
        ("2026.11.0", "2026.11", 0),
        ("6.5.1978688000", "1.70.1970071030", 1),  # Hue bridge build numbers
        ("6.5.1978688000", "1.70.1978688000", 0),
        ("1.9.2 Build 260519", "1.9.2 Build 260519 Rel.40211n", 0),  # TP-Link
        ("1.9.2 Build 260519", "1.9.1 Build 250101 Rel.1", 1),
        ("v3.1.0.4972_2506051567", "v3.1.0.4972_2506051567", 0),  # Reolink
        ("v3.1.0.4972_2506051567", "v3.0.0.4410_2411141903", 1),
        ("10", "0x0000000a", 0),  # Zigbee file version vs ZHA
        ("10", "0x00000009", 1),
        ("27.398.0-82170", "16.4", None),  # Sonos: different numbering, no claim
        ("2.2.1", "Up to date", None),
        ("10", "0.0.0_0010", None),
        ("2026.11.1", "1.2.0", None),
        ("1.0", "", None),
        ("1.2.0", "1.3.0", -1),
    ],
)
def test_compare(latest, installed, expected):
    assert compare(latest, installed) == expected


def test_esphome_project_version():
    assert installed_from_sw_version("1.2.0 (ESPHome 2026.11.1)", "esphome") == "2026.11.1"
    assert installed_from_sw_version("2026.11.1", "esphome") == "2026.11.1"
    assert installed_from_sw_version("1.2.0 (ESPHome 2026.11.1)", "mqtt") == "1.2.0 (ESPHome 2026.11.1)"

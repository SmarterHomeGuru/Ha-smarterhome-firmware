"""The notification blueprint is valid and fires once per new version."""

from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

SRC = Path(__file__).parent.parent / "blueprints" / "automation" / "smarterhome_firmware" / "notify_new_firmware.yaml"


async def test_blueprint_notifies_once(hass: HomeAssistant) -> None:
    dest = Path(hass.config.path("blueprints/automation/smarterhome_firmware"))
    dest.mkdir(parents=True, exist_ok=True)
    # mobile_app can't load in the test harness (camera and voice deps), so the test copy sends
    # through the notify action the device action resolves to. Triggers, conditions and the
    # message templates are the real ones.
    text = SRC.read_text().replace(
        "  - domain: mobile_app\n    type: notify\n    device_id: !input notify_device\n",
        "  - action: notify.mobile_app_robs_phone\n    data:\n",
    )
    text = text.replace("    title: \"{{", "      title: \"{{").replace("    message: >-\n      {%", "      message: >-\n        {%")
    text = text.replace("    data:\n      url:", "      data:\n        url:").replace("      clickAction:", "        clickAction:")
    (dest / SRC.name).write_text(text)

    phone_entry = MockConfigEntry(domain="mobile_app", data={"device_name": "Rob's phone", "webhook_id": "w", "app_id": "a", "app_name": "a", "app_version": "1", "manufacturer": "A", "model": "B", "os_name": "iOS", "os_version": "18", "supports_encryption": False, "device_id": "p1", "secret": None, "user_id": None})
    phone_entry.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(config_entry_id=phone_entry.entry_id, identifiers={("mobile_app", "p1")}, name="Rob's phone")
    calls = async_mock_service(hass, "notify", "mobile_app_robs_phone")

    eid = "update.porch_light_smarterhome_firmware"
    base = {"installed_version": "1.4.4", "title": "All Shelly Gen2+ devices", "tracker_url": "https://www.smarterhome.guru/firmware/shelly/all-shelly-gen2-devices", "owner_reports_ok": 2, "owner_reports_problem": 1}
    hass.states.async_set(eid, "off", {**base, "latest_version": "1.4.4"})

    assert await async_setup_component(
        hass,
        "automation",
        {"automation": {"use_blueprint": {"path": "smarterhome_firmware/notify_new_firmware.yaml", "input": {"firmware_entities": [eid], "notify_device": phone.id, "only_problems": False}}}},
    )
    await hass.async_block_till_done()
    autos = hass.states.async_all("automation")
    assert len(autos) == 1 and autos[0].state == "on", autos

    hass.states.async_set(eid, "on", {**base, "latest_version": "2.2.1"})
    await hass.async_block_till_done()
    assert len(calls) == 1, calls
    assert calls[0].data["title"] == "All Shelly Gen2+ devices 2.2.1 is out"
    assert "1 owner reported problems" in calls[0].data["message"]

    # Attribute-only noise (owner counts change) does not notify again.
    hass.states.async_set(eid, "on", {**base, "latest_version": "2.2.1", "owner_reports_ok": 3})
    await hass.async_block_till_done()
    assert len(calls) == 1

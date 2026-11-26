"""End-to-end: catalog download, matching against the device registry, update entities."""

import json
from pathlib import Path

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smarterhome_firmware.const import CATALOG_URL, CONF_SKIP_COVERED, DOMAIN

CATALOG = json.loads((Path(__file__).parent / "fixtures" / "catalog.json").read_text())


def add_device(hass, domain, ident, **kw):
    other = MockConfigEntry(domain=domain)
    other.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={(domain, ident)}, **kw)


async def setup(hass, aioclient_mock, options=None):
    aioclient_mock.get(CATALOG_URL, json=CATALOG, headers={"ETag": '"abc"'})
    entry = MockConfigEntry(domain=DOMAIN, title="SmarterHome Firmware", options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def update_entity_for(hass, device):
    ents = [e for e in er.async_entries_for_device(er.async_get(hass), device.id) if e.platform == DOMAIN]
    assert len(ents) == 1, ents
    return hass.states.get(ents[0].entity_id)


async def test_entities(hass: HomeAssistant, aioclient_mock, hass_ws_client) -> None:
    gen2 = add_device(hass, "shelly", "a", manufacturer="Shelly", model="Shelly Plus 1PM", model_id="SNSW-001P16EU", sw_version="20241011-114455/1.4.4-g6d2a586", name="Porch light")
    gen1 = add_device(hass, "shelly", "b", manufacturer="Shelly", model="Shelly 1", model_id="SHSW-1", sw_version="20230913-112003/v1.14.0-gcb84623", name="Garage")
    sonos = add_device(hass, "sonos", "c", manufacturer="Sonos", model="Era 100", model_id="S39", sw_version="16.4", name="Kitchen")
    hue_lamp = add_device(hass, "hue", "d", manufacturer="Signify Netherlands B.V.", model="Hue color lamp", model_id="LCT015", sw_version="1.122.2", name="Lamp")
    await setup(hass, aioclient_mock)

    st = update_entity_for(hass, gen2)
    assert st.state == STATE_ON
    assert st.attributes["installed_version"] == "20241011-114455/1.4.4-g6d2a586"
    assert st.attributes["latest_version"] == "2.2.1"
    assert st.attributes["tracker_url"].endswith("/firmware/shelly/all-shelly-gen2-devices")
    assert st.attributes["versions_comparable"] is True
    assert st.attributes["release_summary"]
    assert len(st.attributes["release_summary"]) <= 255
    assert st.attributes["attribution"] == "Firmware data from SmarterHome.guru"

    st = update_entity_for(hass, gen1)
    assert st.state == STATE_OFF  # same version in a different wrapper

    st = update_entity_for(hass, sonos)
    assert st.state == STATE_OFF  # numbering differs: no claim
    assert st.attributes["versions_comparable"] is False

    assert not [e for e in er.async_entries_for_device(er.async_get(hass), hue_lamp.id) if e.platform == DOMAIN]

    client = await hass_ws_client(hass)
    eid = [e for e in er.async_entries_for_device(er.async_get(hass), sonos.id) if e.platform == DOMAIN][0].entity_id
    await client.send_json({"id": 1, "type": "update/release_notes", "entity_id": eid})
    result = await client.receive_json()
    assert result["success"], result
    assert "can't compare" in result["result"]
    assert "smarterhome.guru" in result["result"]

    # A device added later gets an entity too (registry listener, debounced).
    hub = add_device(hass, "reolink", "e", manufacturer="Reolink", model="P330", sw_version="v3.0.0.4410_2411141903", name="Driveway")
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()
    assert update_entity_for(hass, hub).state == STATE_ON

    # The request said nothing about the home.
    for _method, url, data, _headers in aioclient_mock.mock_calls:
        assert str(url) == CATALOG_URL
        assert data is None


async def test_skip_covered(hass: HomeAssistant, aioclient_mock) -> None:
    gen2 = add_device(hass, "shelly", "a", manufacturer="Shelly", model="Shelly Plus 1PM", model_id="SNSW-001P16EU", sw_version="1.4.4")
    er.async_get(hass).async_get_or_create("update", "shelly", "a-fw", device_id=gen2.id)
    await setup(hass, aioclient_mock)
    assert not [e for e in er.async_entries_for_device(er.async_get(hass), gen2.id) if e.platform == DOMAIN]


async def test_keep_covered(hass: HomeAssistant, aioclient_mock) -> None:
    gen2 = add_device(hass, "shelly", "a", manufacturer="Shelly", model="Shelly Plus 1PM", model_id="SNSW-001P16EU", sw_version="1.4.4")
    er.async_get(hass).async_get_or_create("update", "shelly", "a-fw", device_id=gen2.id)
    await setup(hass, aioclient_mock, {CONF_SKIP_COVERED: False})
    assert update_entity_for(hass, gen2).state == STATE_ON


async def test_offline_start_uses_saved_copy(hass: HomeAssistant, aioclient_mock, hass_storage) -> None:
    hass_storage["smarterhome_firmware.catalog"] = {"version": 1, "minor_version": 1, "key": "smarterhome_firmware.catalog", "data": {"etag": '"abc"', "catalog": CATALOG}}
    gen2 = add_device(hass, "shelly", "a", manufacturer="Shelly", model="Shelly Plus 1PM", model_id="SNSW-001P16EU", sw_version="1.4.4")
    aioclient_mock.get(CATALOG_URL, status=500)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert update_entity_for(hass, gen2).state == STATE_ON


async def test_bad_schema_fails_setup_without_cache(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(CATALOG_URL, json={"schema": 99, "devices": []})
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_config_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(CATALOG_URL, json=CATALOG)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "abort"

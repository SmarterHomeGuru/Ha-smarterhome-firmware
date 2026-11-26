"""Diagnostics: which devices matched and which did not (stays on your machine unless you share it)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SmarterHomeConfigEntry
from .matcher import Matcher
from .update import covered_device_ids, ha_devices


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SmarterHomeConfigEntry) -> dict[str, Any]:
    catalog = entry.runtime_data.data or {}
    matcher = Matcher(catalog)
    covered = covered_device_ids(hass)
    matched, unmatched = [], []
    for d in ha_devices(hass, entry.entry_id):
        m = matcher.match(d)
        row = {"manufacturer": d.manufacturer, "model": d.model, "model_id": d.model_id, "sw_version": d.sw_version, "domains": d.domains}
        if m:
            matched.append({**row, "catalog_key": m.key, "method": m.method, "has_own_update_entity": d.id in covered})
        else:
            unmatched.append(row)
    return {
        "catalog_generated": catalog.get("generated"),
        "catalog_devices": len(catalog.get("devices", [])),
        "options": dict(entry.options),
        "matched": matched,
        "unmatched": unmatched,
    }

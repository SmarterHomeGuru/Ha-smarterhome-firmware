"""Firmware update entities, one per Home Assistant device the catalog covers.

These entities only inform: they never install anything. Updating stays with the maker's app
or the device's own integration.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmarterHomeConfigEntry
from .const import ATTRIBUTION, CONF_INCLUDE_BETA, CONF_SKIP_COVERED, DEFAULT_INCLUDE_BETA, DEFAULT_SKIP_COVERED, DOMAIN
from .coordinator import CatalogCoordinator
from .matcher import HaDevice, Match, Matcher
from .versions import compare, installed_from_sw_version

SUMMARY_MAX = 255


def ha_devices(hass: HomeAssistant, own_entry_id: str) -> list[HaDevice]:
    """Every device in the registry with a firmware version, as the matcher wants it."""
    entries = {e.entry_id: e.domain for e in hass.config_entries.async_entries()}
    out = []
    for device in dr.async_get(hass).devices.values():
        if not device.sw_version or device.disabled_by is not None:
            continue
        domains = [entries[i] for i in device.config_entries if i in entries and i != own_entry_id]
        if not domains:
            continue
        out.append(
            HaDevice(
                id=device.id,
                manufacturer=device.manufacturer,
                model=device.model,
                model_id=device.model_id,
                sw_version=device.sw_version,
                domains=domains,
                name=device.name_by_user or device.name,
            )
        )
    return out


def covered_device_ids(hass: HomeAssistant) -> set[str]:
    """Devices that already have an update entity from another integration."""
    return {
        e.device_id
        for e in er.async_get(hass).entities.values()
        if e.domain == "update" and e.platform != DOMAIN and e.device_id and e.disabled_by is None
    }


def find_matches(hass: HomeAssistant, entry: SmarterHomeConfigEntry, catalog: dict[str, Any]) -> list[Match]:
    """Match the registry against the catalog, honouring the skip option."""
    matcher = Matcher(catalog)
    skip = entry.options.get(CONF_SKIP_COVERED, DEFAULT_SKIP_COVERED)
    covered = covered_device_ids(hass) if skip else set()
    matches = []
    for device in ha_devices(hass, entry.entry_id):
        if device.id in covered:
            continue
        m = matcher.match(device)
        if m is not None:
            matches.append(m)
    return matches


async def async_setup_entry(hass: HomeAssistant, entry: SmarterHomeConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Create entities for matched devices, and again whenever devices change."""
    coordinator = entry.runtime_data
    known: dict[str, FirmwareUpdateEntity] = {}

    @callback
    def sync() -> None:
        new = []
        for m in find_matches(hass, entry, coordinator.data):
            entity = known.get(m.device_id)
            if entity is None:
                entity = FirmwareUpdateEntity(coordinator, entry, m)
                known[m.device_id] = entity
                new.append(entity)
            elif entity.match.key != m.key:
                entity.set_match(m)
        if new:
            async_add_entities(new)

    async def _debounced_sync() -> None:
        sync()

    debouncer = Debouncer(hass, None, cooldown=10, immediate=False, function=_debounced_sync)  # type: ignore[arg-type]

    @callback
    def on_registry_change(_event: Event) -> None:
        if hass.state is CoreState.running:
            debouncer.async_schedule_call()

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
    entry.async_on_unload(hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, on_registry_change))
    entry.async_on_unload(debouncer.async_shutdown)
    if hass.state is not CoreState.running:
        # Other integrations may still be adding devices at startup.
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, lambda _e: sync()))


class FirmwareUpdateEntity(CoordinatorEntity[CatalogCoordinator], UpdateEntity):
    """Latest firmware for one device, with notes and owner reports."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: CatalogCoordinator, entry: SmarterHomeConfigEntry, match: Match) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.match = match
        self._attr_unique_id = f"{match.device_id}_firmware"
        device = dr.async_get(coordinator.hass).async_get(match.device_id)
        # Attach to the existing device (shown on its page), never create a new one.
        if device is not None:
            self._attr_device_info = DeviceInfo(identifiers=device.identifiers, connections=device.connections)

    def set_match(self, match: Match) -> None:
        self.match = match
        self.async_write_ha_state()

    # ------------------------------------------------------------------ data

    @property
    def _entry_data(self) -> dict[str, Any] | None:
        for e in self.coordinator.data.get("devices", []):
            if e.get("key") == self.match.key:
                return e
        return None

    @property
    def _release(self) -> dict[str, Any] | None:
        e = self._entry_data
        if e is None:
            return None
        stable, beta = e.get("stable"), e.get("beta")
        if beta and self._entry.options.get(CONF_INCLUDE_BETA, DEFAULT_INCLUDE_BETA) and stable:
            if compare(beta["version"], stable["version"]) == 1:
                return beta
        return stable

    @property
    def _device(self) -> dr.DeviceEntry | None:
        return dr.async_get(self.hass).async_get(self.match.device_id)

    @property
    def _domain(self) -> str | None:
        device = self._device
        if device is None:
            return None
        entries = {e.entry_id: e.domain for e in self.hass.config_entries.async_entries()}
        for entry_id in device.config_entries:
            if entry_id in entries and entries[entry_id] != DOMAIN:
                return entries[entry_id]
        return None

    @property
    def available(self) -> bool:
        return super().available and self._entry_data is not None and self._device is not None

    @property
    def installed_version(self) -> str | None:
        device = self._device
        if device is None or not device.sw_version:
            return None
        return installed_from_sw_version(device.sw_version, self._domain)

    @property
    def latest_version(self) -> str | None:
        release = self._release
        return release["version"] if release else None

    def _compare(self, latest: str | None, installed: str | None) -> int | None:
        """compare(), or None for brands whose HA version can't be lined up with the maker's notes."""
        e = self._entry_data
        brand = {b.get("slug"): b for b in self.coordinator.data.get("brands", [])}.get(e["brand"] if e else None, {})
        if not latest or not installed or brand.get("comparable") is False:
            return None
        return compare(latest, installed)

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        # Unknown or mismatched version formats never count as an update.
        return self._compare(latest_version, installed_version) == 1

    @property
    def title(self) -> str | None:
        e = self._entry_data
        return e["name"] if e else None

    @property
    def release_url(self) -> str | None:
        e = self._entry_data
        return e["url"] if e else None

    @property
    def release_summary(self) -> str | None:
        release = self._release
        if not release:
            return None
        parts = []
        votes = release.get("votes") or {}
        ok, problem = int(votes.get("ok", 0)), int(votes.get("problem", 0))
        if problem:
            parts.append(f"{problem} owner{'s' if problem != 1 else ''} reported problems, {ok} said it worked fine.")
        elif ok:
            parts.append(f"{ok} owner{'s' if ok != 1 else ''} said it worked fine.")
        if release.get("notes"):
            parts.append(release["notes"])
        text = " ".join(parts) or "The maker did not publish details for this version."
        return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1].rsplit(" ", 1)[0] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        release = self._release or {}
        installed, latest = self.installed_version, self.latest_version
        votes = release.get("votes") or {}
        return {
            "tracker_url": self.release_url,
            "released": release.get("released"),
            "owner_reports_ok": int(votes.get("ok", 0)),
            "owner_reports_problem": int(votes.get("problem", 0)),
            "versions_comparable": self._compare(latest, installed) is not None,
            "match_method": self.match.method,
        }

    async def async_release_notes(self) -> str | None:
        release = self._release
        e = self._entry_data
        if not release or not e:
            return None
        lines = [f"**{e['name']} {release['version']}**" + (f", released {release['released']}" if release.get("released") else "")]
        lines.append("")
        lines.append(release.get("notes") or "The maker did not publish details for this version.")
        votes = release.get("votes") or {}
        ok, problem = int(votes.get("ok", 0)), int(votes.get("problem", 0))
        lines.append("")
        if ok or problem:
            lines.append(f"Owner reports on SmarterHome.guru: {ok} worked fine, {problem} had problems.")
        else:
            lines.append("No owner reports yet. Updated already? Tell other owners how it went on the tracker page.")
        installed = self.installed_version
        if installed and self._compare(release["version"], installed) is None:
            lines.append("")
            lines.append(f"Your device reports version {installed}, which we can't compare with the maker's numbering. Check the version in the maker's app.")
        lines.append("")
        links = [f"[Tracker page and history]({e['url']})"]
        if release.get("notes_url"):
            links.append(f"[Maker's release notes]({release['notes_url']})")
        lines.append(" · ".join(links))
        lines.append("")
        lines.append("_Firmware data from [SmarterHome.guru](https://www.smarterhome.guru/firmware). This entity never installs anything._")
        return "\n".join(lines)

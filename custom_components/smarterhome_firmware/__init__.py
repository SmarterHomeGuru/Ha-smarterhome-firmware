"""SmarterHome Firmware: firmware notes and update alerts for the devices Home Assistant knows."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CatalogCoordinator

PLATFORMS = [Platform.UPDATE]

type SmarterHomeConfigEntry = ConfigEntry[CatalogCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SmarterHomeConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = CatalogCoordinator(hass, entry)
    await coordinator.async_load_cached()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: SmarterHomeConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SmarterHomeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

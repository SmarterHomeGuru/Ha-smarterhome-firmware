"""Fetch the SmarterHome.guru firmware catalog."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CATALOG_SCHEMA, CATALOG_URL, DOMAIN, STORAGE_KEY, STORAGE_VERSION, UPDATE_INTERVAL, VERSION

_LOGGER = logging.getLogger(__name__)


class CatalogCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Downloads the catalog every 6 hours.

    The request carries nothing about the home: the same file goes to everyone and matching
    happens here. The last good copy is kept on disk so a restart works offline.
    """

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL, config_entry=config_entry)
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._etag: str | None = None
        self._cached: dict[str, Any] | None = None

    async def async_load_cached(self) -> None:
        """Load the last catalog from disk, if any."""
        saved = await self._store.async_load()
        if saved and isinstance(saved.get("catalog"), dict):
            self._cached = saved["catalog"]
            self._etag = saved.get("etag")

    async def _async_update_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        headers = {"User-Agent": f"SmarterHomeFirmware/{VERSION} HomeAssistant/{HA_VERSION}", "Accept": "application/json"}
        if self._etag and self._cached is not None:
            headers["If-None-Match"] = self._etag
        try:
            async with session.get(CATALOG_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 304 and self._cached is not None:
                    return self._cached
                resp.raise_for_status()
                catalog = await resp.json(content_type=None)
                etag = resp.headers.get("ETag")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            if self._cached is not None:
                _LOGGER.warning("Could not refresh the SmarterHome firmware catalog, using the saved copy: %s", err)
                return self._cached
            raise UpdateFailed(f"Could not download the firmware catalog: {err}") from err
        if not isinstance(catalog, dict) or catalog.get("schema") != CATALOG_SCHEMA or not isinstance(catalog.get("devices"), list):
            if self._cached is not None:
                _LOGGER.warning("The firmware catalog has an unexpected format; using the saved copy")
                return self._cached
            raise UpdateFailed("The firmware catalog has an unexpected format; this version of the integration may need an update")
        self._cached, self._etag = catalog, etag
        await self._store.async_save({"etag": etag, "catalog": catalog})
        return catalog

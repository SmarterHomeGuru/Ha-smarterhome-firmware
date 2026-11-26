"""Constants for SmarterHome Firmware."""

from datetime import timedelta

DOMAIN = "smarterhome_firmware"
NAME = "SmarterHome Firmware"
VERSION = "0.1.0"

CATALOG_URL = "https://www.smarterhome.guru/api/firmware-catalog.json"
CATALOG_SCHEMA = 1
UPDATE_INTERVAL = timedelta(hours=6)
STORAGE_KEY = f"{DOMAIN}.catalog"
STORAGE_VERSION = 1

CONF_INCLUDE_BETA = "include_beta"
CONF_SKIP_COVERED = "skip_covered"
DEFAULT_INCLUDE_BETA = False
DEFAULT_SKIP_COVERED = True

ATTRIBUTION = "Firmware data from SmarterHome.guru"

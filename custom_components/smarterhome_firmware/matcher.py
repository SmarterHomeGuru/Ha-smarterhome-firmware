"""Match Home Assistant devices to SmarterHome.guru catalog entries.

Pure Python (no Home Assistant imports) so it can be tested on its own. Everything runs on
the user's machine: the catalog is the same public file for everyone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def norm(value: str | None) -> str:
    """Lowercase letters and digits only: "Signify Netherlands B.V." -> "signifynetherlandsbv"."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


@dataclass
class HaDevice:
    """What we need from a device registry entry."""

    id: str
    manufacturer: str | None
    model: str | None
    model_id: str | None
    sw_version: str | None
    domains: list[str] = field(default_factory=list)
    name: str | None = None


@dataclass(frozen=True)
class Match:
    """A Home Assistant device paired with a catalog entry, and how we decided."""

    device_id: str
    key: str
    method: str  # rule, domain, model, single, fallback


class Matcher:
    """Index of a catalog for fast lookups."""

    def __init__(self, catalog: dict[str, Any]) -> None:
        self.entries: dict[str, dict[str, Any]] = {e["key"]: e for e in catalog.get("devices", [])}
        self.brands: dict[str, dict[str, Any]] = {b["slug"]: b for b in catalog.get("brands", [])}
        self._alias: dict[str, set[str]] = {}
        self._domain: dict[str, str] = {}
        self._rules: list[tuple[str, str, str]] = []
        self._models: dict[str, dict[str, set[str]]] = {}
        self._by_brand: dict[str, list[str]] = {}

        for slug, brand in self.brands.items():
            for alias in [brand.get("name", ""), *brand.get("aliases", [])]:
                if norm(alias):
                    self._alias.setdefault(norm(alias), set()).add(slug)
        for key, entry in self.entries.items():
            brand = entry["brand"]
            self._by_brand.setdefault(brand, []).append(key)
            for domain in entry.get("domains", []):
                self._domain[domain] = key
            for rule in entry.get("rules", []):
                self._rules.append((norm(rule.get("manufacturer")), norm(rule.get("model")), key))
            brand_words = [norm(w) for w in re.split(r"[\s\-]+", self.brands.get(brand, {}).get("name", "")) if len(w) >= 3]
            index = self._models.setdefault(brand, {})
            for model in entry.get("models", []):
                n = norm(model)
                if len(n) < 2:
                    continue
                index.setdefault(n, set()).add(key)
                # "Tapo C310" should also match HA's "C310".
                for word in brand_words:
                    if n.startswith(word) and len(n) - len(word) >= 2:
                        index.setdefault(n[len(word):], set()).add(key)

    def _brands_for(self, manufacturer: str | None) -> set[str]:
        n = norm(manufacturer)
        if not n:
            return set()
        if n in self._alias:
            return set(self._alias[n])
        found: set[str] = set()
        for alias, slugs in self._alias.items():
            # "Signify Netherlands B.V." starts with "signify"; ignore very short aliases.
            if len(alias) >= 4 and n.startswith(alias):
                found |= slugs
        return found

    def _newest(self, keys: set[str]) -> str:
        """Several entries list the same model (overlapping Sonos groups): take the newest release."""
        def sort_key(k: str) -> tuple[str, str]:
            stable = self.entries[k].get("stable") or {}
            return (stable.get("released") or stable.get("first_seen") or "", k)
        return max(keys, key=sort_key)

    def match(self, device: HaDevice) -> Match | None:
        """Find the catalog entry for one device, or None."""
        if not device.sw_version:
            return None
        man, mod = norm(device.manufacturer), norm(device.model)
        for r_man, r_mod, key in self._rules:
            if man == r_man and mod == r_mod:
                return Match(device.id, key, "rule")
        for domain in device.domains:
            if domain in self._domain:
                return Match(device.id, self._domain[domain], "domain")
        brands = self._brands_for(device.manufacturer)
        if not brands:
            return None
        hits: set[str] = set()
        for value in (device.model_id, device.model):
            n = norm(value)
            if len(n) < 2:
                continue
            for brand in brands:
                hits |= self._models.get(brand, {}).get(n, set())
            if hits:
                break
        if hits:
            return Match(device.id, self._newest(hits), "model")
        candidates = [k for b in brands for k in self._by_brand.get(b, [])]
        if len(candidates) == 1:
            return Match(device.id, candidates[0], "single")
        for brand in sorted(brands):
            info = self.brands.get(brand, {})
            fallback = info.get("fallback")
            skip = info.get("fallback_skip")
            # The skip pattern reads the model id (Shelly Gen1 "SHSW-1"); without one we can't tell, so no fallback.
            if skip and (not device.model_id or re.search(skip, device.model_id)):
                continue
            if fallback and fallback in self.entries:
                return Match(device.id, fallback, "fallback")
        return None

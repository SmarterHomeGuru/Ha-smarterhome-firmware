"""Compare firmware version strings from different makers.

Makers write versions in many shapes ("v1.14.0-gcb84623", "1.9.2 Build 260519",
"6.5.1978688000", "0x0000000a"), and Home Assistant integrations sometimes report a
different shape than the maker's release notes. A wrong "update available" is worse
than none, so compare() returns None whenever the two strings are not clearly the same
kind of version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DOTTED = re.compile(r"(?<![\d.])(\d+(?:\.\d+)+)")
_BUILD = re.compile(r"(?:build|rel\.?|[-_])\s*(\d{4,})", re.IGNORECASE)
_HEX = re.compile(r"^0x([0-9a-f]+)$", re.IGNORECASE)
_INT = re.compile(r"^v?(\d+)$", re.IGNORECASE)
_ESPHOME = re.compile(r"\(ESPHome ([0-9][0-9A-Za-z.\-]*)\)")

# A component this long is a build number (Hue "1.70.1970071030"), not a release counter.
_LONG_BUILD = 7


@dataclass(frozen=True)
class Parsed:
    """The comparable parts of a version string."""

    dotted: tuple[int, ...] = ()
    build: int | None = None
    integer: int | None = None


def installed_from_sw_version(sw_version: str, domain: str | None = None) -> str:
    """The firmware version inside a device's sw_version.

    ESPHome nodes with a project version report "1.2.0 (ESPHome 2026.11.1)"; the ESPHome
    release is the part we track.
    """
    if domain == "esphome":
        m = _ESPHOME.search(sw_version)
        if m:
            return m.group(1)
    return sw_version.strip()


def parse(version: str) -> Parsed:
    """Pull out the dotted release number, a build number, or a plain integer."""
    v = version.strip()
    m = _HEX.match(v)
    if m:
        return Parsed(integer=int(m.group(1), 16))
    m = _INT.match(v)
    if m:
        return Parsed(integer=int(m.group(1)))
    dotted: tuple[int, ...] = ()
    rest = v
    m = _DOTTED.search(v)
    if m:
        dotted = tuple(int(p) for p in m.group(1).split("."))
        rest = v[m.end():]
    build = None
    b = _BUILD.search(rest)
    if b:
        build = int(b.group(1))
    return Parsed(dotted=dotted, build=build)


def _cmp(a: tuple[int, ...] | int, b: tuple[int, ...] | int) -> int:
    return (a > b) - (a < b)


def compare(latest: str, installed: str) -> int | None:
    """1 if latest is newer than installed, 0 if the same, -1 if older, None if unknown."""
    if not latest or not installed:
        return None
    if latest.strip().lower().lstrip("v") == installed.strip().lower().lstrip("v"):
        return 0
    a, b = parse(latest), parse(installed)

    # Plain integers (Zigbee file versions) only compare with each other.
    if a.integer is not None or b.integer is not None:
        if a.integer is not None and b.integer is not None:
            return _cmp(a.integer, b.integer)
        return None
    if not a.dotted or not b.dotted:
        return None

    # Long build numbers in the last place: compare those alone (Hue bridge).
    if a.dotted[-1] >= 10**(_LONG_BUILD - 1) and b.dotted[-1] >= 10**(_LONG_BUILD - 1):
        return _cmp(a.dotted[-1], b.dotted[-1])

    # Same shape only: "2.2.1" vs "1.4.4" yes, "27.398.0" vs "17.4" no.
    if len(a.dotted) != len(b.dotted):
        # Allow a trailing ".0" difference ("2026.11" vs "2026.11.0").
        short, long_ = sorted((a.dotted, b.dotted), key=len)
        if len(long_) - len(short) == 1 and long_[-1] == 0 and long_[:-1] == short:
            return 0 if a.build is None or b.build is None else _cmp(a.build, b.build)
        return None
    if max(a.dotted[0], b.dotted[0]) > 10 * max(1, min(a.dotted[0], b.dotted[0])) and min(a.dotted[0], b.dotted[0]) > 0:
        # Different numbering schemes (a year-based "2026.11.1" vs "1.2.0").
        return None
    result = _cmp(a.dotted, b.dotted)
    if result == 0 and a.build is not None and b.build is not None:
        return _cmp(a.build, b.build)
    return result

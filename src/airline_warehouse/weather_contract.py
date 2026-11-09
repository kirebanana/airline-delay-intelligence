"""Versioned local scope and fail-closed scheduled-time classification.

No database or network access. The January ISD implementation remains unchanged.
"""

import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

LEGACY_CONTRACT = "den-isd-aviation-qc15-independent-60m-v1"
CONTRACT = "den-ghcnh-aviation-independent-60m-v2"
REFERENCE = Path(__file__).resolve().parents[2] / "references/den-ghcnh-weather-v2.json"
TIMEZONE_FILE = Path("/usr/share/zoneinfo/America/Denver")


def mapping_sha256():
    return hashlib.sha256(REFERENCE.read_bytes()).hexdigest()


def reference():
    return json.loads(REFERENCE.read_text())


def contract_scope(manifest):
    """Return canonical scope dictionary; reject inconsistent identity/bounds.

    Legacy manifests predate explicit local scope fields. Those two fields alone
    may be absent for v1; every v2 field below is mandatory.
    """
    contract = manifest.get("contract")
    if contract == CONTRACT:
        ref = reference()
        keys = ("scope_start", "scope_end_exclusive", "start", "end", "station", "origin_id")
        expected = {key: ref[key] for key in keys}
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("GHCNh scope/identity mismatch")
    elif contract == LEGACY_CONTRACT:
        expected = {
            "scope_start": "2025-01-01",
            "scope_end_exclusive": "2025-02-01",
            "start": "2025-01-01T06:00:00+00:00",
            "end": "2025-02-01T07:00:00+00:00",
            "station": "72565003017",
            "origin_id": 11292,
        }
        for key, value in expected.items():
            if key.startswith("scope_") and key not in manifest:
                continue
            if manifest.get(key) != value:
                raise ValueError("ISD scope/identity mismatch")
    else:
        raise ValueError("Unknown weather contract")
    return expected


def verify_mapping(manifest):
    """Verify v2 mapping, scope and pinned timezone bytes, returning its scope."""
    scope = contract_scope(manifest)
    ref = reference()
    if (
        manifest.get("contract") != CONTRACT
        or manifest.get("mapping_version") != ref["version"]
        or manifest.get("mapping_sha256") != mapping_sha256()
        or manifest.get("origin_sequences") != ref["origin_sequences"]
        or manifest.get("timezone") != ref["timezone"]
        or manifest.get("timezone_sha256") != ref["timezone_sha256"]
        or hashlib.sha256(TIMEZONE_FILE.read_bytes()).hexdigest() != ref["timezone_sha256"]
    ):
        raise ValueError("GHCNh mapping/timezone dependency changed")
    return scope


def classify_scheduled_anchor(date, clock, manifest):
    """Return (UTC datetime | None, status), never choosing a DST fold.

    Invalid dates/clocks/mappings are integrity errors (raise), not time waivers.
    Only ambiguous_local_time, nonexistent_local_time and unresolved_midnight
    are counted-but-unmatchable schedule exceptions under v2.
    """
    scope = contract_scope(manifest)
    if manifest["contract"] == LEGACY_CONTRACT:
        from airline_warehouse.weather import scheduled_anchor as legacy_anchor

        return legacy_anchor(date, clock), "resolved"
    verify_mapping(manifest)
    day = dt.date.fromisoformat(date)
    if not scope["scope_start"] <= day.isoformat() < scope["scope_end_exclusive"]:
        raise ValueError("Scheduled date outside contract scope")
    if not isinstance(clock, str) or not re.fullmatch(r"[0-9]{1,4}", clock):
        raise ValueError("Malformed scheduled local clock")
    hour, minute = divmod(int(clock), 100)
    if (hour, minute) == (24, 0) or (hour, minute) == (0, 0):
        return None, "unresolved_midnight"
    if hour > 23 or minute > 59:
        raise ValueError("Malformed scheduled local clock")
    zone = ZoneInfo.from_file(io.BytesIO(TIMEZONE_FILE.read_bytes()), key="America/Denver")
    local = dt.datetime.combine(day, dt.time(hour, minute))
    candidates = set()
    for fold in (0, 1):
        utc = local.replace(tzinfo=zone, fold=fold).astimezone(dt.UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(utc)
    if not candidates:
        return None, "nonexistent_local_time"
    if len(candidates) > 1:
        return None, "ambiguous_local_time"
    return candidates.pop(), "resolved"


def scheduled_anchor(date, clock, manifest):
    """Convenience nullable UTC anchor; use classifier to preserve reason codes."""
    return classify_scheduled_anchor(date, clock, manifest)[0]

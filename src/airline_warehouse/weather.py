"""Bounded ISD input adapter for the fixed DEN/local-January pilot.

Decoding/provenance belong here; variable-specific backward matching and reusable
analytical meaning belong in dbt. No automatic download or annual-file fallback.
"""

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

STATION = "72565003017"
START = dt.datetime(2025, 1, 1, 6, tzinfo=dt.UTC)
END = dt.datetime(2025, 2, 1, 7, tzinfo=dt.UTC)
CONTRACT = "den-isd-aviation-qc15-independent-60m-v1"
VARIABLES = ("temperature", "wind", "visibility")
REFERENCE = Path(__file__).resolve().parents[2] / "references/den-weather-pilot.json"


def scheduled_anchor(date, clock):
    """R06 snapshot rule: new midnight ambiguities require review, not rollover."""
    day = dt.date.fromisoformat(date)
    if not dt.date(2025, 1, 1) <= day < dt.date(2025, 2, 1):
        raise ValueError("Outside the fixed Denver-local January pilot")
    if not re.fullmatch(r"[0-9]{1,4}", clock):
        raise ValueError("Malformed scheduled local clock")
    hour, minute = divmod(int(clock), 100)
    if hour > 23 or minute > 59 or (hour, minute) == (0, 0):
        raise ValueError("Unresolved midnight or malformed scheduled clock")
    return dt.datetime.combine(day, dt.time(hour, minute), ZoneInfo("America/Denver")).astimezone(
        dt.UTC
    )


def decode(variable, raw):
    parts = raw.split(",")
    index, qc_index, size, sentinel, scale, low, high = {
        "temperature": (0, 1, 2, "+9999", 10, -932, 618),
        "wind": (3, 4, 5, "9999", 10, 0, 900),
        "visibility": (0, 1, 4, "999999", 1, 0, 160000),
    }[variable]
    pattern = {"temperature": r"[-+][0-9]{4}", "wind": r"[0-9]{4}", "visibility": r"[0-9]{6}"}[
        variable
    ]
    if len(parts) != size or not re.fullmatch(pattern, parts[index]):
        return None, "malformed"
    if parts[index] == sentinel:
        return None, "missing"
    value = int(parts[index])
    if not low <= value <= high:
        return None, "malformed"
    if parts[qc_index] not in {"1", "5"}:
        return None, "rejected_qc"
    return value / scale, "accepted"


def parse_observations(stream, source_sha):
    reader = csv.reader(stream)
    header = next(reader)
    required = {"STATION", "DATE", "REPORT_TYPE", "CALL_SIGN", "TMP", "WND", "VIS"}
    if not required <= set(header):
        raise ValueError("Missing required NOAA columns")
    grouped = {}
    for ordinal, cells in enumerate(reader, 1):
        if len(cells) != len(header):
            raise ValueError("NOAA row width mismatch")
        row = {}
        for name, value in zip(header, cells, strict=True):
            if name in row and row[name] != value:
                raise ValueError("Repeated NOAA header values disagree")
            row[name] = value
        if row["STATION"] != STATION:
            raise ValueError("Unexpected NOAA station")
        stamp = dt.datetime.fromisoformat(row["DATE"])
        stamp = stamp.replace(tzinfo=dt.UTC) if stamp.tzinfo is None else stamp.astimezone(dt.UTC)
        if not START <= stamp < END:
            continue  # held January-UTC input; exact pilot selection remains explicit
        if row["REPORT_TYPE"] not in ("FM-15", "FM-16"):
            continue
        if row["CALL_SIGN"].strip() != "KDEN":
            raise ValueError("Historical aviation station/call-sign mapping mismatch")
        for variable, field in zip(VARIABLES, ("TMP", "WND", "VIS"), strict=True):
            value, status = decode(variable, row[field])
            grouped.setdefault((stamp.isoformat(), variable), []).append(
                {
                    "value": value,
                    "status": status,
                    "raw": row[field],
                    "source_sha256": source_sha,
                    "source_row": ordinal,
                    "report_type": row["REPORT_TYPE"],
                }
            )
    result = []
    for (stamp, variable), reports in sorted(grouped.items()):
        good = {r["value"] for r in reports if r["status"] == "accepted"}
        if len(good) > 1:
            raise ValueError("Conflicting accepted station/time/variable measurements")
        chosen = next((r for r in reports if r["status"] == "accepted"), reports[0])
        result.append(
            {
                "station": STATION,
                "observed_at": stamp,
                "variable": variable,
                "value": chosen["value"],
                "status": chosen["status"],
                "duplicate_count": len(reports),
                "provenance": reports,
            }
        )
    return result


def prepare_weather(sources, output):
    """Explicit [(path, expected checksum)] imports; original files remain preserved."""
    output = Path(output)
    if output.exists() or not 1 <= len(sources) <= 2:
        raise ValueError("Weather requires create-only output and one/two bounded imports")
    rows, identities = [], []
    for path, expected in sources:
        path = Path(path)
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("Weather input exceeds the five-MiB per-file envelope")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != expected:
            raise ValueError("Weather source checksum mismatch")
        identities.append(checksum)
        with path.open(newline="") as stream:
            rows.extend(parse_observations(stream, checksum))
    keys = [(r["observed_at"], r["variable"]) for r in rows]
    if not rows or len(rows) > 10000 or len(set(keys)) != len(keys):
        raise ValueError("Empty/oversized weather or overlapping input windows")
    payload = "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
        for r in sorted(rows, key=lambda r: (r["observed_at"], r["variable"]))
    )
    timezone_hash = hashlib.sha256(
        Path("/usr/share/zoneinfo/America/Denver").read_bytes()
    ).hexdigest()
    manifest = {
        "contract": CONTRACT,
        "sources": identities,
        "rows": len(rows),
        "mapping_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "timezone_sha256": timezone_hash,
        "timezone": "America/Denver",
        "station": STATION,
        "origin_id": 11292,
        "origin_sequence": "1129202",
        "start": START.isoformat(),
        "end": END.isoformat(),
    }
    manifest["weather_id"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    output.mkdir(parents=True)
    (output / "observations.jsonl").write_text(payload)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_weather(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    claimed = manifest.pop("weather_id")
    actual = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    manifest["weather_id"] = claimed
    if (
        actual != claimed
        or manifest["contract"] != CONTRACT
        or manifest.get("mapping_sha256") != hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
        or not re.fullmatch(r"[a-f0-9]{64}", claimed)
        or hashlib.sha256((path / "observations.jsonl").read_bytes()).hexdigest()
        != manifest["payload_sha256"]
    ):
        raise ValueError("Incompatible or corrupt weather dependency")
    rows = (path / "observations.jsonl").read_text().splitlines()
    if len(rows) != manifest["rows"] or not 0 < len(rows) <= 10000:
        raise ValueError("Weather row count mismatch")
    return manifest, rows


def load_weather(connection, path):
    """Create-only small reference input; exact content comparison on replay."""
    manifest, rows = read_weather(path)
    table = "AIRLINE_DB.RAW.WEATHER_" + manifest["weather_id"][:32].upper()
    with connection.cursor() as cur:
        cur.execute(
            f"CREATE TRANSIENT TABLE IF NOT EXISTS {table} (record VARCHAR NOT NULL) "
            "DATA_RETENTION_TIME_IN_DAYS=0"
        )
        cur.execute(f"SELECT record FROM {table} LIMIT 10001")
        existing = [r[0] for r in cur.fetchall()]
        if not existing:
            cur.execute("BEGIN TRANSACTION")
            try:
                for start in range(0, len(rows), 200):
                    batch = rows[start : start + 200]
                    cur.execute(
                        f"INSERT INTO {table} SELECT column1 FROM VALUES "
                        + ",".join(["(%s)"] * len(batch)),
                        batch,
                    )
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            cur.execute(f"SELECT record FROM {table} LIMIT 10001")
            existing = [r[0] for r in cur.fetchall()]
        if sorted(existing) != sorted(rows):
            raise ValueError("Existing weather input is incomplete or incompatible; no overwrite")
    return manifest, table


def render_weather_sql(name, schema):
    """Same versioned dbt definitions, rebound only to the frozen allowlisted set."""
    from jinja2 import Environment, StrictUndefined

    if name not in ("weather_observations", "den_weather", "weather_integrity"):
        raise ValueError("Unknown weather SQL contract")
    if not re.fullmatch(r"(?:WORK|RELEASE)_[A-F0-9]{24}", schema):
        raise ValueError("Unknown isolated schema")
    root = Path(__file__).resolve().parents[2] / "dbt"
    folder = "tests" if name == "weather_integrity" else "models"
    return (
        Environment(undefined=StrictUndefined)
        .from_string((root / folder / (name + ".sql")).read_text())
        .render(
            config=lambda **kw: "",
            var=lambda *a: True,
            ref=lambda n: f"AIRLINE_DB.{schema}.{n.upper()}",
            source=lambda *a: (
                f"(SELECT preserved_record AS record FROM AIRLINE_DB.{schema}.WEATHER_OBSERVATIONS)"
            ),
        )
    )


def validate_frozen_weather(connection, schema, manifest):
    """Complete input digest, field reconstruction, backward join and all-row gates."""
    timezone_hash = hashlib.sha256(
        Path("/usr/share/zoneinfo/America/Denver").read_bytes()
    ).hexdigest()
    if (
        manifest.get("contract") != CONTRACT
        or manifest.get("timezone_sha256") != timezone_hash
        or manifest.get("mapping_sha256") != hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    ):
        raise ValueError("Weather timezone/processing dependency changed")
    prefix = f"AIRLINE_DB.{schema}."
    with connection.cursor() as cur:
        cur.execute(f"SELECT preserved_record FROM {prefix}WEATHER_OBSERVATIONS LIMIT 10001")
        records = [r[0] for r in cur.fetchall()]
        ordered = sorted(
            records, key=lambda r: (json.loads(r)["observed_at"], json.loads(r)["variable"])
        )
        payload = "".join(r + "\n" for r in ordered)
        if (
            len(records) != manifest["rows"]
            or hashlib.sha256(payload.encode()).hexdigest() != manifest["payload_sha256"]
        ):
            raise ValueError("Frozen weather input provenance/checksum mismatch")
        for model in ("weather_observations", "den_weather"):
            expected = render_weather_sql(model, schema)
            cur.execute(
                f"WITH expected AS ({expected}) "
                f"SELECT * FROM (SELECT * FROM {prefix}{model.upper()} "
                "MINUS SELECT * FROM expected) "
                "UNION ALL SELECT * FROM (SELECT * FROM expected "
                f"MINUS SELECT * FROM {prefix}{model.upper()})"
            )
            if cur.fetchone() is not None:
                raise ValueError("Frozen weather field/match reconstruction failed")
        cur.execute(render_weather_sql("weather_integrity", schema))
        if cur.fetchone() is not None:
            raise ValueError("Frozen weather population/coverage gate failed")
        cur.execute(
            f"SELECT source_date,source_clock,scheduled_utc FROM {prefix}DEN_WEATHER LIMIT 100001"
        )
        anchors = cur.fetchall()
        if not 0 < len(anchors) <= 100000:
            raise ValueError("Unexpected pilot population bound")
        for date, clock, actual in anchors:
            if actual is None or actual.replace(tzinfo=dt.UTC) != scheduled_anchor(date, clock):
                raise ValueError("Frozen anchor differs from pinned America/Denver timezone")

"""Explicit raw artifact loads: no analytics, publication or automated corrections.

One immutable table per prepared artifact. COPY is strict, never FORCE/TRUNCATE,
and acceptance is independently checked inside its explicit transaction. Existing
tables must match the exact artifact metadata; ambiguous outcomes require inspection.
"""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from airline_warehouse.prepare import BTS_COLUMNS, CONTRACT, LINEAGE, sha256_file


def validate_manifest(m: dict) -> None:
    if (
        m.get("manifest_version") != 1
        or m.get("preparation_contract") != CONTRACT
        or m.get("source_columns") != BTS_COLUMNS
        or m.get("prepared_columns") != LINEAGE + BTS_COLUMNS
        or m.get("source_kind") not in ("official-local-import", "synthetic-fixture")
        or not isinstance(m.get("rows"), int)
        or not 0 < m["rows"] <= 1_000_000
        or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", m.get("month", ""))
    ):
        raise ValueError("Unsupported or incomplete preparation manifest")
    for key in ("source_sha256", "prepared_sha256", "loaded_artifact_id"):
        if not re.fullmatch(r"[a-f0-9]{64}", m.get(key, "")):
            raise ValueError(f"Invalid {key}")
    expected = hashlib.sha256(
        f"{m['source_sha256']}:{CONTRACT}:{m['prepared_sha256']}".encode("ascii")
    ).hexdigest()
    if m["loaded_artifact_id"] != expected:
        raise ValueError("Loaded artifact identity does not match manifest dependencies")


def object_keys(m: dict) -> dict[str, str]:
    validate_manifest(m)
    source = f"bts/{m['month']}/{m['source_sha256']}"
    prepared = f"prepared/{source}/{m['loaded_artifact_id']}"
    return {
        "source": f"original/{source}/source.zip",
        "prepared": f"{prepared}/prepared.csv.gz",
        "manifest": f"manifests/{prepared}.json",
    }


def build_load_plan(m: dict, bucket: str) -> dict:
    validate_manifest(m)
    if bucket != "airline-bts-336805808138-us-east-2":
        raise ValueError("Bucket must be an explicit project bucket in the approved account/region")
    schema = "INGEST_TEST" if m["source_kind"] == "synthetic-fixture" else "RAW"
    suffix = f"{m['month'].replace('-', '')}_{m['loaded_artifact_id'][:32].upper()}"
    table = f"AIRLINE_DB.{schema}.BTS_{suffix}"
    columns = ",\n  ".join(
        f'"{n}" {"NUMBER(38,0)" if n == "SOURCE_ROW_NUMBER" else "VARCHAR"} NOT NULL'
        for n in LINEAGE + BTS_COLUMNS
    )
    comment = json.dumps(
        {
            "artifact": m["loaded_artifact_id"],
            "source": m["source_sha256"],
            "prepared": m["prepared_sha256"],
            "rows": m["rows"],
        },
        sort_keys=True,
    )
    key = object_keys(m)["prepared"]
    # External stage points to prepared/ only; no arbitrary URL, filename or SQL input.
    relative_key = key.removeprefix("prepared/")
    names = ", ".join(f'"{n}"' for n in LINEAGE + BTS_COLUMNS)
    row_text = ", ".join(f'LENGTH("{n}")::VARCHAR || \':\' || "{n}"' for n in BTS_COLUMNS)
    source = m["source_sha256"]
    return {
        "table": table,
        "expected_rows": m["rows"],
        "bucket": bucket,
        "object_key": key,
        "table_comment": comment,
        "create_sql": f"CREATE TRANSIENT TABLE IF NOT EXISTS {table} (\n  {columns}\n) "
        f"DATA_RETENTION_TIME_IN_DAYS=0 COMMENT='{comment}'",
        "copy_sql": f"COPY INTO {table} ({names})\n"
        f"FROM @AIRLINE_DB.RAW.BTS_EXTERNAL_STAGE\nFILES = ('{relative_key}')\n"
        "FILE_FORMAT=(FORMAT_NAME='AIRLINE_DB.RAW.BTS_CSV_V1')\n"
        "ON_ERROR = 'ABORT_STATEMENT' FORCE = FALSE PURGE = FALSE",
        "validation_sql": f"""SELECT COUNT(*) AS "ROWS",
COUNT(DISTINCT "SOURCE_ROW_NUMBER") AS DISTINCT_ORDINALS,
MIN("SOURCE_ROW_NUMBER") AS FIRST_ORDINAL, MAX("SOURCE_ROW_NUMBER") AS LAST_ORDINAL,
COUNT_IF("SOURCE_SHA256" <> '{source}') AS WRONG_SOURCE,
COUNT_IF(LEFT("FlightDate",7) <> '{m["month"]}') AS WRONG_MONTH,
COUNT_IF("OriginAirportID"='11292') AS DEN_ROWS,
COUNT_IF("OriginAirportID"='11292' AND "Cancelled"='1.00') AS DEN_CANCELLED,
COUNT_IF("OriginAirportID"='11292' AND "Diverted"='1.00') AS DEN_DIVERTED,
COUNT_IF(SHA2(CONCAT_WS('', {row_text}),256) <> "SOURCE_ROW_SHA256") AS MISMATCHED_FINGERPRINTS
FROM {table}""",
    }


def check_validation(row: dict, manifest: dict) -> None:
    expected = {
        "ROWS": manifest["rows"],
        "DISTINCT_ORDINALS": manifest["rows"],
        "FIRST_ORDINAL": 1,
        "LAST_ORDINAL": manifest["rows"],
        "WRONG_SOURCE": 0,
        "WRONG_MONTH": 0,
        "MISMATCHED_FINGERPRINTS": 0,
        "DEN_ROWS": manifest["profile"]["den_rows"],
        "DEN_CANCELLED": manifest["profile"]["den_cancelled"],
        "DEN_DIVERTED": manifest["profile"]["den_diverted"],
    }
    # COUNT_IF may return NULL when no rows qualify.
    if not expected.keys() <= row.keys() or any(
        (row[key] or 0) != value for key, value in expected.items()
    ):
        raise ValueError("Raw acceptance failed: count/ordinal/source/month/fingerprint mismatch")


def read_artifact(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    validate_manifest(manifest)
    if sha256_file(directory / "prepared.csv.gz") != manifest["prepared_sha256"]:
        raise ValueError("Prepared file checksum mismatch; refuse upload/load")
    return manifest


def check_account_monitor(monitor: dict) -> None:
    """Inspect existing protection only; never create, attach or alter a monitor."""
    try:
        quota = Decimal(str(monitor["credit_quota"]))
        used = Decimal(str(monitor["used_credits"]))
        suspend = Decimal(str(monitor["suspend_at"]).removesuffix("%"))
        immediate = Decimal(str(monitor["suspend_immediate_at"]).removesuffix("%"))
        valid = (
            monitor["name"] == "AIRLINE_BUDGET"
            and monitor["level"] == "ACCOUNT"
            and all(v.is_finite() for v in (quota, used, suspend, immediate))
            and quota > 0
            and used >= 0
            and 0 < suspend <= immediate <= 100
            and used < quota * suspend / 100
        )
    except (KeyError, InvalidOperation):
        valid = False
    if not valid:
        raise ValueError("Account monitor quota/suspension protection is unavailable or exhausted")


def execute_load(connection, manifest: dict, bucket: str, *, funding_verified: bool) -> dict:
    """Explicit invocation after funding approval; callers provide a scoped connection.

    No retry after unknown COMMIT/client failure. The immutable table can be checked
    with validation_sql before another attempt; no publication reference is involved.
    """
    plan = build_load_plan(manifest, bucket)
    if not funding_verified:
        raise ValueError("Funding/entitlement must be verified before a live raw load")
    query_ids = []
    with connection.cursor() as cur:
        cur.execute("SHOW WAREHOUSES LIKE 'AIRLINE_DEV_WH'")
        names = [c[0].lower() for c in cur.description]
        warehouses = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        if len(warehouses) != 1:
            raise ValueError("Expected exact project warehouse")
        wh = warehouses[0]
        if (
            wh["size"] != "X-Small"
            or not 0 < int(wh["auto_suspend"]) <= 60
            or str(wh["enable_query_acceleration"]).lower() != "false"
        ):
            raise ValueError("Project warehouse cost controls are not ready; refusing load")
        cur.execute("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
        names = [c[0].lower() for c in cur.description]
        monitors = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        monitors = [m for m in monitors if m.get("name") == "AIRLINE_BUDGET"]
        if len(monitors) != 1:
            raise ValueError(
                "Account monitor is not visible; owner verification/access is required"
            )
        check_account_monitor(monitors[0])
        cur.execute("USE WAREHOUSE AIRLINE_DEV_WH")
        cur.execute(
            "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=600, "
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=60, LOCK_TIMEOUT=10, "
            "QUERY_TAG='airline:raw-ingest:v1'"
        )
        cur.execute(plan["create_sql"])
        cur.execute(
            f"SHOW TABLES LIKE '{plan['table'].split('.')[-1]}' "
            f"IN SCHEMA {'.'.join(plan['table'].split('.')[:2])}"
        )
        columns = [c[0].lower() for c in cur.description]
        existing = [dict(zip(columns, r, strict=True)) for r in cur.fetchall()]
        if len(existing) != 1 or existing[0]["comment"] != plan["table_comment"]:
            raise ValueError("Existing raw object does not match the complete artifact identity")
        # COPY history expires: verify existing data, not just historical filenames.
        # Reuse complete artifacts; never append to or silently repair a partial one.
        cur.execute(plan["validation_sql"])
        fields = [c[0] for c in cur.description]
        before = dict(zip(fields, cur.fetchone(), strict=True))
        if before.get("ROWS", 0) != 0:
            check_validation(before, manifest)
            return {
                "status": "reused",
                "artifact": manifest["loaded_artifact_id"],
                "table": plan["table"],
                "validation": before,
                "query_ids": [cur.sfqid],
            }
        cur.execute("BEGIN")
        try:
            cur.execute(plan["copy_sql"])
            query_ids.append(cur.sfqid)
            copy_result = cur.fetchall()
            cur.execute(plan["validation_sql"])
            query_ids.append(cur.sfqid)
            fields = [c[0] for c in cur.description]
            validation = dict(zip(fields, cur.fetchone(), strict=True))
            check_validation(validation, manifest)
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        # A lost COMMIT acknowledgment is deliberately NOT automatically retried.
        cur.execute("COMMIT")
        return {
            "status": "accepted",
            "artifact": manifest["loaded_artifact_id"],
            "table": plan["table"],
            "validation": validation,
            "copy_result": copy_result,
            "query_ids": query_ids,
        }

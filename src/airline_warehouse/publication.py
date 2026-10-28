"""Lock-first target authority and frozen releases. No automatic uncertain-work takeover.

One trusted local runner owns each connection. Callers must await/terminate all
data-capable work before retiring a failed run. Publisher ownership is not WORM.
"""

import json
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

from airline_warehouse.deadlines import DeadlineConnection


class Busy(ValueError):
    pass


class Stale(ValueError):
    pass


class CommitUnknown(RuntimeError):
    """Reconcile exact identity on a fresh connection; never blindly retry."""


def _target(target):
    if not isinstance(target, str) or not re.fullmatch(r"(?:january|test_[a-f0-9]{16})", target):
        raise ValueError("Unknown approved publication target")


def _hex(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Expected immutable 32-hex identity")


def _rows(cur):
    return [
        dict(zip([c[0].lower() for c in cur.description], row, strict=True))
        for row in cur.fetchall()
    ]


@contextmanager
def _locked(connection, target):
    _target(target)
    with connection.cursor() as cur:
        cur.execute("BEGIN TRANSACTION")
        try:
            # Real write precedes authority reads. Standard-table locks may be table-wide.
            cur.execute(
                "UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard=guard+1 WHERE target=%s", (target,)
            )
            if cur.rowcount != 1:
                raise Stale("Target singleton cardinality mismatch")
            cur.execute(
                "SELECT *, deadline>CURRENT_TIMESTAMP() AS in_time "
                "FROM AIRLINE_DB.CONTROL.TARGETS WHERE target=%s",
                (target,),
            )
            rows = _rows(cur)
            if len(rows) != 1:
                raise Stale("Target singleton cardinality mismatch")
            yield cur, rows[0]
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        try:
            cur.execute("COMMIT")
        except BaseException as error:
            raise CommitUnknown(
                "Commit acknowledgment unknown; reconcile exact request/release"
            ) from error


def initialize(connection, target):
    """Attended versioned migration/bootstrap, separate from runtime transactions."""
    _target(target)
    sql = (Path(__file__).resolve().parents[2] / "sql/07_publication.sql").read_text()
    with connection.cursor() as cur:
        for statement in sql.split(";"):
            if statement.strip():
                cur.execute(statement)
        cur.execute("BEGIN TRANSACTION")
        try:
            cur.execute("UPDATE AIRLINE_DB.CONTROL.MIGRATION_GUARD SET guard=guard+1")
            if cur.rowcount != 1:
                raise Stale("Migration guard cardinality mismatch")
            cur.execute(
                "SELECT COUNT(*) FROM AIRLINE_DB.CONTROL.TARGETS WHERE target=%s", (target,)
            )
            count = cur.fetchone()[0]
            if count == 0:
                cur.execute(
                    "INSERT INTO AIRLINE_DB.CONTROL.TARGETS "
                    "(target,guard,fence,epoch,cancelled) VALUES (%s,0,0,0,FALSE)",
                    (target,),
                )
            elif count != 1:
                raise Stale("Target singleton cardinality mismatch")
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        cur.execute("COMMIT")


def _authority(row, token, *, allow_cancelled=False):
    if (
        row["owner"] != token["attempt"]
        or row["request_id"] != token["request_id"]
        or row["fence"] != token["fence"]
        or (not allow_cancelled and (row["cancelled"] or not row["in_time"]))
    ):
        raise Stale("Attempt retired, cancelled, stale or past its absolute deadline")


def claim(connection, target, request_id, *, attempt=None):
    _hex(request_id)
    if attempt is not None:
        _hex(attempt)
    with _locked(connection, target) as (cur, row):
        cur.execute(
            "SELECT * FROM AIRLINE_DB.CONTROL.RUNS WHERE target=%s AND request_id=%s",
            (target, request_id),
        )
        runs = _rows(cur)
        if len(runs) > 1:
            raise Stale("Request registry cardinality mismatch")
        if runs:
            return {k: runs[0][k] for k in ("target", "request_id", "attempt", "fence", "status")}
        if row["owner"] is not None:
            raise Busy("Target claimed; uncertain work requires attended recovery, not takeover")
        attempt, fence = attempt or uuid.uuid4().hex, row["fence"] + 1
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET owner=%s,request_id=%s,fence=%s,"
            "cancelled=FALSE,deadline=DATEADD(minute,45,CURRENT_TIMESTAMP()) WHERE target=%s",
            (attempt, request_id, fence, target),
        )
        cur.execute(
            "INSERT INTO AIRLINE_DB.CONTROL.RUNS "
            "(target,request_id,attempt,fence,status) VALUES (%s,%s,%s,%s,'RUNNING')",
            (target, request_id, attempt, fence),
        )
        return dict(
            target=target, request_id=request_id, attempt=attempt, fence=fence, status="RUNNING"
        )


def retire(connection, token, status):
    """Only after synchronous data work is terminal; never use for uncertain work."""
    if status not in ("FAILED", "CANCELLED"):
        raise ValueError("Invalid terminal failure status")
    with _locked(connection, token["target"]) as (cur, row):
        _authority(row, token, allow_cancelled=True)
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.RUNS SET status=%s "
            "WHERE target=%s AND request_id=%s AND attempt=%s AND status='RUNNING'",
            (status, token["target"], token["request_id"], token["attempt"]),
        )
        if cur.rowcount != 1:
            raise Stale("Run registry cardinality mismatch")
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET owner=NULL,request_id=NULL WHERE target=%s",
            (token["target"],),
        )


def cancel(connection, token):
    with _locked(connection, token["target"]) as (cur, row):
        _authority(row, token, allow_cancelled=True)
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET cancelled=TRUE WHERE target=%s",
            (token["target"],),
        )


def _validate_frozen(connection, schema, candidate):
    """Validate every row/table of the frozen declared set, not just work metadata."""
    from airline_warehouse.prepare import BTS_COLUMNS

    root = Path(__file__).resolve().parents[2]
    sql = (root / "dbt/tests/candidate_integrity.sql").read_text()
    sql = re.sub(
        r"\{\{ ref\('(fact_flights|stg_flights)'\) \}\}", f"AIRLINE_DB.{schema}.FACT_FLIGHTS", sql
    )
    sql = sql.replace("{{ var('expected_rows',0) }}", str(candidate["expected_rows"]))
    with connection.cursor() as cur:
        derived = (root / "dbt/tests/derived_consistency.sql").read_text()
        derived = re.sub(
            r"\{\{ ref\('([a-z_]+)'\) \}\}",
            lambda m: f"AIRLINE_DB.{schema}.{m[1].upper()}",
            derived,
        )
        cur.execute(derived)
        if cur.fetchone() is not None:
            raise ValueError("Frozen derived metric/source reconciliation failed")
        cur.execute(sql)
        if cur.fetchone() is not None:
            raise ValueError("Frozen critical quality contract failed")
        table = f"AIRLINE_DB.{schema}.FACT_FLIGHTS"
        expression = ", ".join(f'LENGTH("{n}")::VARCHAR || \':\' || "{n}"' for n in BTS_COLUMNS)
        cur.execute(
            f"SELECT COUNT(*),COUNT(DISTINCT flight_key),"
            f"COALESCE(COUNT_IF(COALESCE(SHA2(CONCAT_WS('',{expression}),256)"
            f'<>"SOURCE_ROW_SHA256",TRUE)),0) FROM {table}'
        )
        if cur.fetchone() != (candidate["expected_rows"], candidate["expected_rows"], 0):
            raise ValueError("Frozen row/key/source-value integrity mismatch")
        cur.execute(f"SELECT loaded_artifact_id,COUNT(*) FROM {table} GROUP BY 1")
        if {r[0] for r in cur.fetchall()} != set(candidate["inputs"].values()):
            raise ValueError("Frozen selected artifact identity mismatch")
        for dimension, key, refs in (
            ("DIM_DATE", "date_key", ("flight_date",)),
            ("DIM_AIRPORT", "airport_id", ("origin_id", "destination_id")),
            ("DIM_CARRIER", "carrier_id", ("marketing_carrier_id", "operating_carrier_id")),
        ):
            dim = f"AIRLINE_DB.{schema}.{dimension}"
            cur.execute(f"SELECT COUNT(*),COUNT({key}),COUNT(DISTINCT {key}) FROM {dim}")
            n, known, distinct = cur.fetchone()
            if not n or n != known or n != distinct:
                raise ValueError("Frozen dimension uniqueness/null contract failed")
            for ref in refs:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} f LEFT JOIN {dim} d "
                    f"ON f.{ref}=d.{key} WHERE d.{key} IS NULL"
                )
                if cur.fetchone()[0]:
                    raise ValueError("Frozen relationship contract failed")
        cur.execute(f"SHOW TABLES IN SCHEMA AIRLINE_DB.{schema}")
        tables = _rows(cur)
        if len(tables) != 4 or any(
            t["kind"] != "TRANSIENT" or str(t["retention_time"]) != "1" for t in tables
        ):
            raise ValueError("Frozen lifecycle contract failed")


def publish(connection, token, candidate, release_id, *, timeout_seconds=300, evidence_path=None):
    """Snapshot DDL first, validate frozen data, then atomic registry/pointer commit.

    Persist release_id BEFORE calling. Any uncertain exception requires exact
    reconciliation and terminal-query inspection; never replay this create-only job.
    """
    from airline_warehouse.analytics import relation

    _hex(release_id)
    if not 1 <= timeout_seconds <= 300:
        raise ValueError("Publication timeout must fit the approved five-minute bound")
    with connection.cursor() as cur:
        cur.execute(f"ALTER SESSION SET QUERY_TAG='airline:publication:{release_id}'")
    connection = DeadlineConnection(connection, timeout_seconds, evidence_path)
    relation(candidate, development=True)
    if type(candidate.get("expected_rows")) is not int or candidate["expected_rows"] <= 0:
        raise ValueError("Invalid candidate population")
    schema = "RELEASE_" + release_id[:24].upper()
    with _locked(connection, token["target"]) as (cur, row):
        _authority(row, token)
        cur.execute(
            "SELECT COUNT(*) FROM AIRLINE_DB.CONTROL.RELEASES WHERE release_id=%s", (release_id,)
        )
        if cur.fetchone()[0]:
            raise Stale("Release identity already used; reconcile instead of replay")
    with connection.cursor() as cur:
        cur.execute(f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{schema} DATA_RETENTION_TIME_IN_DAYS=1")
        for table in ("FACT_FLIGHTS", "DIM_DATE", "DIM_AIRPORT", "DIM_CARRIER"):
            cur.execute(
                f"CREATE TRANSIENT TABLE AIRLINE_DB.{schema}.{table} "
                f"CLONE AIRLINE_DB.{candidate['schema']}.{table}"
            )
    _validate_frozen(connection, schema, candidate)
    with connection.cursor() as cur:
        cur.execute(f"GRANT USAGE ON SCHEMA AIRLINE_DB.{schema} TO ROLE AIRLINE_READER_ROLE")
        for view, table in (
            ("FLIGHTS", "FACT_FLIGHTS"),
            ("DATES", "DIM_DATE"),
            ("AIRPORTS", "DIM_AIRPORT"),
            ("CARRIERS", "DIM_CARRIER"),
        ):
            cur.execute(
                f"CREATE VIEW AIRLINE_DB.{schema}.{view} AS "
                f"SELECT * FROM AIRLINE_DB.{schema}.{table}"
            )
            cur.execute(
                f"GRANT SELECT ON VIEW AIRLINE_DB.{schema}.{view} TO ROLE AIRLINE_READER_ROLE"
            )
        cur.execute("SELECT CURRENT_TIMESTAMP()")
        published_at = cur.fetchone()[0].isoformat()
    descriptor = {
        k: candidate[k] for k in ("inputs", "expected_rows", "processing_contract", "built_at")
    }
    descriptor.update(
        schema=schema,
        target=token["target"],
        release_id=release_id,
        sealed=True,
        published_at=published_at,
    )
    with _locked(connection, token["target"]) as (cur, row):
        _authority(row, token)
        cur.execute(
            "SELECT COUNT(*) FROM AIRLINE_DB.CONTROL.RELEASES WHERE release_id=%s", (release_id,)
        )
        if cur.fetchone()[0]:
            raise Stale("Release registry identity collision")
        cur.execute(
            "INSERT INTO AIRLINE_DB.CONTROL.RELEASES "
            "(target,release_id,attempt,descriptor) VALUES (%s,%s,%s,%s)",
            (token["target"], release_id, token["attempt"], json.dumps(descriptor, sort_keys=True)),
        )
        if row["active"] is not None:
            cur.execute(
                "UPDATE AIRLINE_DB.CONTROL.RELEASES SET "
                "retired_until=DATEADD(hour,24,CURRENT_TIMESTAMP()) "
                "WHERE target=%s AND release_id=%s",
                (token["target"], row["active"]),
            )
            if cur.rowcount != 1:
                raise Stale("Active registry cardinality mismatch")
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.RUNS SET status='PUBLISHED',release_id=%s "
            "WHERE target=%s AND request_id=%s AND attempt=%s AND status='RUNNING'",
            (release_id, token["target"], token["request_id"], token["attempt"]),
        )
        if cur.rowcount != 1:
            raise Stale("Run registry cardinality mismatch")
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET previous=active,active=%s,epoch=epoch+1,"
            "owner=NULL,request_id=NULL WHERE target=%s",
            (release_id, token["target"]),
        )
    return descriptor


def reconcile(connection, token, release_id):
    """Read exact committed identity; absence never authorizes an automatic retry."""
    _hex(release_id)
    with _locked(connection, token["target"]) as (cur, row):
        cur.execute(
            "SELECT descriptor,attempt FROM AIRLINE_DB.CONTROL.RELEASES "
            "WHERE target=%s AND release_id=%s",
            (token["target"], release_id),
        )
        rows = cur.fetchall()
        if len(rows) == 1 and rows[0][1] == token["attempt"]:
            return json.loads(rows[0][0])
        raise Stale("Publication not proven committed; reconcile terminal work before recovery")


def request_result(connection, target, request_id):
    _target(target)
    _hex(request_id)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT r.descriptor FROM AIRLINE_DB.CONTROL.RUNS u "
            "JOIN AIRLINE_DB.CONTROL.RELEASES r "
            "ON u.target=r.target AND u.release_id=r.release_id "
            "WHERE u.target=%s AND u.request_id=%s AND u.status='PUBLISHED'",
            (target, request_id),
        )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise Stale("Request has no singleton committed result; no automatic duplicate writer")
    return json.loads(rows[0][0])


def reuse_active(connection, token, inputs, contract):
    """Exact input/processing replay is a no-op: retire new authority, keep epoch."""
    with _locked(connection, token["target"]) as (cur, row):
        _authority(row, token)
        if row["active"] is None:
            return None
        cur.execute(
            "SELECT descriptor FROM AIRLINE_DB.CONTROL.RELEASES WHERE target=%s AND release_id=%s",
            (token["target"], row["active"]),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            raise Stale("Active registry cardinality mismatch")
        descriptor = json.loads(rows[0][0])
        if descriptor["inputs"] != inputs or descriptor["processing_contract"] != contract:
            return None
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.RUNS SET status='PUBLISHED',release_id=%s "
            "WHERE target=%s AND request_id=%s AND attempt=%s AND status='RUNNING'",
            (row["active"], token["target"], token["request_id"], token["attempt"]),
        )
        if cur.rowcount != 1:
            raise Stale("Run registry cardinality mismatch")
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET owner=NULL,request_id=NULL WHERE target=%s",
            (token["target"],),
        )
        return descriptor


def active_release(connection, target):
    _target(target)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT descriptor FROM AIRLINE_DB.CONTROL.READABLE_RELEASES "
            "WHERE target=%s AND is_active",
            (target,),
        )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise Stale("No singleton validated active release")
    return json.loads(rows[0][0])


def validate_reader_token(connection, descriptor):
    _target(descriptor["target"])
    _hex(descriptor["release_id"])
    with connection.cursor() as cur:
        cur.execute(
            "SELECT descriptor FROM AIRLINE_DB.CONTROL.READABLE_RELEASES "
            "WHERE target=%s AND release_id=%s",
            (descriptor["target"], descriptor["release_id"]),
        )
        rows = cur.fetchall()
    if len(rows) != 1 or json.loads(rows[0][0]) != descriptor:
        raise Stale("Release token expired or changed; explicitly reload")

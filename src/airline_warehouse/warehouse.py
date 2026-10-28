"""Selected immutable raw inputs -> isolated, tested dimensional candidate."""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import uuid
from pathlib import Path

from airline_warehouse.budget import live_budget, mark_recovery
from airline_warehouse.connection import connect
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.load import build_load_plan, check_validation

BUCKET = "airline-bts-336805808138-us-east-2"


class RecoveryRequired(RuntimeError):
    """No blind retry: reconcile the exact attempt and its SQL before more work."""


def candidate_plan(manifests: list[dict], schema: str) -> dict:
    if not re.fullmatch(r"WORK_[A-F0-9]{24}", schema):
        raise ValueError("Candidate requires a create-only WORK_<24 hex> schema")
    if not manifests or len(manifests) > 36:
        raise ValueError("Select explicit bounded input months")
    inputs, tables, rows = {}, [], 0
    for manifest in manifests:
        load = build_load_plan(manifest, BUCKET)
        month = manifest["month"]
        if month in inputs:
            raise ValueError("Select exactly one accepted artifact per month")
        inputs[month] = manifest["loaded_artifact_id"]
        tables.append(load["table"])
        rows += manifest["rows"]
    return {"schema": schema, "inputs": inputs, "raw_tables": tables, "expected_rows": rows}


def processing_contract():
    project = Path(__file__).resolve().parents[2] / "dbt"
    digest = hashlib.sha256()
    for p in sorted(project.rglob("*")):
        if p.is_file() and p.suffix in (".sql", ".yml") and not set(p.parts) & {"target", "logs"}:
            digest.update(str(p.relative_to(project)).encode())
            digest.update(p.read_bytes())
    for name in ("dbt_runner.py", "deadlines.py"):
        digest.update(name.encode())
        digest.update((Path(__file__).parent / name).read_bytes())
    digest.update((project.parent / "uv.lock").read_bytes())
    return digest.hexdigest()


def build_candidate(manifests: list[dict], output: Path, budget_path: Path) -> dict:
    """Create-only build. Non-success never emits a sealed candidate descriptor."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Candidate output already exists; do not overwrite accepted artifacts")
    schema = "WORK_" + uuid.uuid4().hex[:24].upper()
    plan = candidate_plan(manifests, schema)
    project = Path(__file__).resolve().parents[2] / "dbt"
    contract = processing_contract()
    output.mkdir(parents=True)
    env = os.environ.copy()
    config = tomllib.loads((Path.home() / ".snowflake/config.toml").read_text())
    env.update(
        AIRLINE_DBT_KEY=config["connections"]["airline"]["private_key_file"],
        AIRLINE_DBT_SCHEMA=schema,
        AIRLINE_QUERY_TAG="airline:batch05-10:" + schema,
    )
    started = time.monotonic()
    sql_started = False
    try:
        with connect() as conn, live_budget(conn, budget_path) as remaining:
            deadline = time.monotonic() + remaining
            env["AIRLINE_DBT_DEADLINE"] = str(deadline)
            with DeadlineConnection(conn, remaining, deadline=deadline).cursor() as cur:
                sql_started = True
                cur.execute("USE SECONDARY ROLES NONE")
                cur.execute(
                    "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=600, "
                    "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=60, LOCK_TIMEOUT=5, "
                    f"QUERY_TAG='{env['AIRLINE_QUERY_TAG']}'"
                )
                for m in manifests:
                    load = build_load_plan(m, BUCKET)
                    cur.execute(load["validation_sql"])
                    check_validation(
                        dict(zip([c[0] for c in cur.description], cur.fetchone(), strict=True)), m
                    )
                cur.execute(
                    f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{schema} DATA_RETENTION_TIME_IN_DAYS=1"
                )
                selects = [
                    f"SELECT r.*, '{m['loaded_artifact_id']}' AS loaded_artifact_id FROM {table} r"
                    for m, table in zip(manifests, plan["raw_tables"], strict=True)
                ]
                cur.execute(
                    f"CREATE VIEW AIRLINE_DB.{schema}.SELECTED_RAW AS "
                    + " UNION ALL ".join(selects)
                )
            command = [
                sys.executable,
                "-m",
                "airline_warehouse.dbt_runner",
                "build",
                "--project-dir",
                str(project),
                "--profiles-dir",
                str(project),
                "--target-path",
                str(output / "dbt"),
                "--log-path",
                str(output / "logs"),
                "--vars",
                json.dumps({"expected_rows": plan["expected_rows"]}),
            ]
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                timeout=max(1, deadline - time.monotonic()),
            )
            (output / "build.log").write_text(result.stdout + result.stderr)
            if result.returncode:
                results_path = output / "dbt/run_results.json"
                statuses = (
                    {r["status"] for r in json.loads(results_path.read_text())["results"]}
                    if results_path.exists()
                    else set()
                )
                if not statuses or not statuses <= {"pass", "success", "fail", "skipped"}:
                    raise RecoveryRequired(
                        "Uncertain dbt failure; inspect exact query tag before retry"
                    )
                raise ValueError("dbt build failed; candidate is not sealed. Inspect its build.log")
            statuses = {
                r["status"]
                for r in json.loads((output / "dbt/run_results.json").read_text())["results"]
            }
            if not statuses or not statuses <= {"pass", "success"}:
                raise RecoveryRequired("Incomplete dbt outcome; refuse to seal candidate")
        descriptor = {
            **plan,
            "processing_contract": contract,
            "sealed": True,
            "tables": ["FACT_FLIGHTS", "DIM_DATE", "DIM_AIRPORT", "DIM_CARRIER"],
            "built_at": dt.datetime.now(dt.UTC).isoformat(),
            "elapsed_seconds": time.monotonic() - started,
        }
        (output / "candidate.json").write_text(json.dumps(descriptor, indent=2) + "\n")
        return descriptor
    except BaseException as error:
        uncertain = sql_started and not isinstance(error, ValueError)
        if uncertain:
            mark_recovery(budget_path, uncertain_schema=schema, query_tag=env["AIRLINE_QUERY_TAG"])
        (output / "failure.json").write_text(
            json.dumps(
                {
                    "status": "RECOVERY_REQUIRED" if uncertain else "UNACCEPTED",
                    "schema": schema,
                    "query_tag": env["AIRLINE_QUERY_TAG"],
                    "message": "Inspect exact attempt; unknown work requires recovery",
                }
            )
            + "\n"
        )
        raise


def grant_candidate(connection, candidate: dict, role: str):
    """Owner grants exact sealed-candidate reads; no role hierarchy/future grants."""
    if role not in ("AIRLINE_PUBLISHER_ROLE", "AIRLINE_READER_ROLE"):
        raise ValueError("Only the reviewed publisher/development-reader roles are allowed")
    schema = candidate["schema"]
    if not candidate.get("sealed") or not re.fullmatch(r"WORK_[A-F0-9]{24}", schema):
        raise ValueError("Only a sealed candidate can be granted")
    tables = (
        ("FACT_FLIGHTS",)
        if role == "AIRLINE_READER_ROLE"
        else ("FACT_FLIGHTS", "DIM_DATE", "DIM_AIRPORT", "DIM_CARRIER")
    )
    with connection.cursor() as cur:
        cur.execute(f"GRANT USAGE ON SCHEMA AIRLINE_DB.{schema} TO ROLE {role}")
        for table in tables:
            cur.execute(f"GRANT SELECT ON TABLE AIRLINE_DB.{schema}.{table} TO ROLE {role}")

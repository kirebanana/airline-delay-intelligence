"""Explicit isolated client-death qualification, never part of ordinary refresh.

Holds one exact test-target guard write and submits a fixed 120-second read, then
hard-exits only after durable session/query evidence. Attended recovery must prove
the ECS producer terminal, abort the originating session/transaction and reconcile
the matching claim. No arbitrary SQL, target initialization or publication.
"""

import json
import logging
import os
import re
import signal
import tempfile
import time
from pathlib import Path

from airline_warehouse.budget import live_budget
from airline_warehouse.cloud_artifacts import ReportStore
from airline_warehouse.cloud_stage import task_identity
from airline_warehouse.connection import connect_as
from airline_warehouse.connectivity_probe import sdk_factory
from airline_warehouse.execution import tracked


def validate_request(request, now):
    if not isinstance(request, dict) or set(request) != {
        "request_id",
        "target",
        "authority",
        "deadline_epoch",
        "budget",
        "task_definition_arn",
    }:
        raise ValueError("Exact attended transaction-probe request required")
    if (
        not isinstance(request["request_id"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", request["request_id"])
        or not isinstance(request["target"], str)
        or not re.fullmatch(r"test_[a-f0-9]{16}", request["target"])
        or type(request["deadline_epoch"]) is not int
        or not 0 < request["deadline_epoch"] - now <= 180
        or not re.fullmatch(
            r"arn:aws:ecs:us-east-2:336805808138:task-definition/"
            r"airline-transaction-qualification:[1-9][0-9]*",
            str(request["task_definition_arn"]),
        )
    ):
        raise ValueError("Wrong isolated scope, task revision or finite deadline")
    token = request["authority"]
    if (
        not isinstance(token, dict)
        or token.get("target") != request["target"]
        or token.get("request_id") != request["request_id"]
        or token.get("attempt") != request["request_id"]
        or token.get("status") != "RUNNING"
        or type(token.get("fence")) is not int
        or token["fence"] < 1
    ):
        raise ValueError("Matching attended claim authority required")
    budget = request["budget"]
    if (
        not isinstance(budget, dict)
        or budget.get("operation_active")
        or budget.get("recovery_required")
        or str(budget.get("recovery_reserve_credits")) != "0.5"
    ):
        raise ValueError("Original unblocked cumulative budget and reserve required")
    return request


def submit_probe(connection, journal, token, deadline):
    bounded = tracked(connection, 180, journal, "publisher", deadline=deadline)
    with bounded.cursor() as cur:
        cur.execute("BEGIN TRANSACTION")
        cur.execute(
            "SELECT guard FROM AIRLINE_DB.CONTROL.TARGETS "
            "WHERE target=%s AND owner=%s AND request_id=%s AND fence=%s",
            (token["target"], token["attempt"], token["request_id"], token["fence"]),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Probe does not own its exact target generation")
        guard = row[0]
        cur.execute(
            "UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard=guard+1 "
            "WHERE target=%s AND owner=%s AND request_id=%s AND fence=%s",
            (token["target"], token["attempt"], token["request_id"], token["fence"]),
        )
        if cur.rowcount != 1:
            raise ValueError("Unexpected probe target cardinality")
        cur.execute(
            "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=120, "
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=5, LOCK_TIMEOUT=5, ABORT_DETACHED_QUERY=FALSE"
        )
    with connection.cursor() as cursor:
        journal.execute(
            cursor.execute_async,
            cursor,
            connection.session_id,
            "SELECT SYSTEM$WAIT(120)",
            timeout=5,
            _statement_params={
                "STATEMENT_TIMEOUT_IN_SECONDS": 120,
                "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 5,
                "LOCK_TIMEOUT": 5,
            },
        )
        return {
            "session_id": connection.session_id,
            "query_id": cursor.sfqid,
            "guard_before_uncommitted_write": guard,
            "statement_ceiling_seconds": 120,
        }


def main():
    logging.disable(logging.CRITICAL)

    def expired(signum, frame):
        raise TimeoutError("Transaction probe absolute deadline exhausted")

    try:
        if os.environ.get("AIRLINE_CLOUD_IDENTITY") != "publisher":
            raise ValueError("Only the exact publisher task identity may run this qualification")
        raw = os.environ.get("AIRLINE_TRANSACTION_PROBE", "")
        if not 0 < len(raw.encode()) <= 5500:
            raise ValueError("Bounded explicit probe request required")
        request = validate_request(json.loads(raw), time.time())
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request["deadline_epoch"] - time.time())
        deadline = time.monotonic() + request["deadline_epoch"] - time.time()
        task = task_identity({"task_definition_arn": request["task_definition_arn"]})
        store = ReportStore(sdk_factory("s3", 5), "publisher", request["request_id"])
        store.write(
            "transaction-probe-intent.json",
            {"task_arn": task, "target": request["target"], "request_id": request["request_id"]},
        )
        with tempfile.TemporaryDirectory(prefix="transaction-probe-") as tmp:
            root = Path(tmp)
            path = root / "budget.json"
            path.write_text(json.dumps(request["budget"]))
            journal = store.journal(root / "work.jsonl", deadline=deadline)
            with (
                connect_as("publisher", deadline=deadline) as conn,
                live_budget(
                    conn,
                    path,
                    deadline=deadline,
                    work_id=request["request_id"],
                    operation_seconds=180,
                ),
            ):
                evidence = submit_probe(conn, journal, request["authority"], deadline)
                store.write(
                    "transaction-probe-submitted.json",
                    {
                        **evidence,
                        "task_arn": task,
                        "target": request["target"],
                        "request_id": request["request_id"],
                        "outcome": "INTENTIONALLY_UNCOMMITTED_CLIENT_DEATH",
                    },
                )
                os._exit(31)  # deliberate: no COMMIT/ROLLBACK/connection-close finally
    except Exception as error:
        print(json.dumps({"status": "RECOVERY_REQUIRED", "error_type": type(error).__name__}))
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())

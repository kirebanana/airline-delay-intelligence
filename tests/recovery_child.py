"""Controlled process-death fixture. Only called by the funded recovery suite."""

import json
import os
import sys
from pathlib import Path

from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.execution import WorkJournal, producer_lock, tracked
from airline_warehouse.publication import claim


def main():
    output, budget = map(Path, sys.argv[1:3])
    intent = json.loads((output / "intent.json").read_text())
    journal = WorkJournal(output / "work.jsonl")
    with producer_lock(journal.path):
        with (
            connect_as("publisher") as conn,
            live_budget(conn, budget, work_id=intent["request_id"]) as remaining,
        ):
            token = claim(
                tracked(conn, remaining, journal, "publisher"),
                intent["target"],
                intent["request_id"],
                attempt=intent["attempt"],
            )
            (output / "authority.json").write_text(json.dumps(token))
        with (
            connect_as("builder") as conn,
            live_budget(conn, budget, work_id=intent["request_id"]) as remaining,
        ):
            bounded = tracked(conn, remaining, journal, "builder")
            table = "AIRLINE_DB.INGEST_TEST.RECOVERY_" + intent["attempt"][:24].upper()
            with bounded.cursor() as cur:
                cur.execute(f"CREATE TRANSIENT TABLE {table} (n NUMBER)")
                cur.execute("BEGIN TRANSACTION")
                cur.execute(f"INSERT INTO {table} VALUES(1)")
                cur.execute("SELECT CURRENT_TRANSACTION()")
                transaction = cur.fetchone()[0]
                cur.execute(
                    "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=5, "
                    "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=5, ABORT_DETACHED_QUERY=FALSE"
                )
            with conn.cursor() as cur:
                sql = "SELECT SYSTEM$WAIT(30)"
                if os.environ.get("AIRLINE_TEST_LOST_QUERY_ID"):
                    journal.append(
                        "query_intent",
                        statement="lost-id-fixture",
                        session_id=conn.session_id,
                        operation="SELECT",
                    )
                    cur.execute_async(sql)
                else:
                    journal.execute(cur.execute_async, cur, conn.session_id, sql)
                (output / "submitted.json").write_text(
                    json.dumps(
                        dict(
                            query_id=cur.sfqid,
                            table=table,
                            transaction=transaction,
                            session_id=conn.session_id,
                        )
                    )
                )
                os._exit(79)  # deliberately bypass all Python/connector cleanup


if __name__ == "__main__":
    main()

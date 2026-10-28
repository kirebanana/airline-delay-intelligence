"""Funded real-Snowflake acceptance at the refresh/publication/read seams."""

import datetime as dt
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as


class SQLFaultConnection:
    """Transport boundary fault: execute real SQL, then lose its response."""

    def __init__(self, connection, hook):
        self.connection, self.hook = connection, hook

    def cursor(self):
        return SQLFaultCursor(self.connection.cursor(), self.hook)


class SQLFaultCursor:
    def __init__(self, cursor, hook):
        self.cursor, self.hook = cursor, hook

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, *args, **kwargs):
        self.cursor.execute(sql, *args, **kwargs)
        self.hook(sql)
        return self


@unittest.skipUnless(
    os.environ.get("AIRLINE_ANALYTICS_LIVE") == "funded-05-10",
    "Requires explicit funded publication qualification",
)
class PublicationTests(unittest.TestCase):
    def test_derived_only_corruption_is_not_published(self):
        from airline_warehouse.publication import (
            Stale,
            active_release,
            claim,
            initialize,
            publish,
            retire,
        )
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        source = candidate["schema"]
        candidate["schema"] = "WORK_" + uuid.uuid4().hex[:24].upper()
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
        ):
            with builder.cursor() as cur:
                cur.execute(
                    f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{candidate['schema']} "
                    "DATA_RETENTION_TIME_IN_DAYS=1"
                )
                for table in ("FACT_FLIGHTS", "DIM_DATE", "DIM_AIRPORT", "DIM_CARRIER"):
                    cur.execute(
                        f"CREATE TRANSIENT TABLE AIRLINE_DB.{candidate['schema']}.{table} "
                        f"CLONE AIRLINE_DB.{source}.{table}"
                    )
                cur.execute(
                    f"UPDATE AIRLINE_DB.{candidate['schema']}.FACT_FLIGHTS "
                    "SET arrival_eligible=FALSE,arrival_delay=42"
                )
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            initialize(conn, target)
            token = claim(conn, target, uuid.uuid4().hex)
            try:
                with self.assertRaisesRegex(ValueError, "derived"):
                    publish(conn, token, candidate, uuid.uuid4().hex)
                with self.assertRaises(Stale):
                    active_release(conn, target)
            finally:
                retire(conn, token, "FAILED")

    def test_duplicate_target_rows_are_rejected_and_whole_transaction_rolls_back(self):
        from airline_warehouse.publication import Stale, claim, initialize, retire

        target = "test_" + uuid.uuid4().hex[:16]
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
        ):
            initialize(conn, target)

            def duplicate(sql):
                if sql.startswith("UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard"):
                    with conn.cursor() as extra:
                        extra.execute(
                            "INSERT INTO AIRLINE_DB.CONTROL.TARGETS "
                            "SELECT * FROM AIRLINE_DB.CONTROL.TARGETS WHERE target=%s",
                            (target,),
                        )

            with self.assertRaises(Stale):
                claim(SQLFaultConnection(conn, duplicate), target, uuid.uuid4().hex)
            token = claim(conn, target, uuid.uuid4().hex)
            retire(conn, token, "FAILED")

    def test_publication_transaction_failures_and_cancellation_during_snapshot(self):
        from airline_warehouse.publication import (
            Stale,
            active_release,
            cancel,
            claim,
            initialize,
            publish,
            retire,
        )
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
            connect_as("publisher") as canceller,
        ):
            initialize(conn, target)
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            for marker in (
                "INSERT INTO AIRLINE_DB.CONTROL.RELEASES",
                "UPDATE AIRLINE_DB.CONTROL.RUNS SET status='PUBLISHED'",
                "UPDATE AIRLINE_DB.CONTROL.TARGETS SET previous=active",
            ):
                token = claim(conn, target, uuid.uuid4().hex)

                def fail(sql, marker=marker):
                    if sql.startswith(marker):
                        raise RuntimeError("Injected publish-transaction response failure")

                with self.assertRaises(RuntimeError):
                    publish(SQLFaultConnection(conn, fail), token, candidate, uuid.uuid4().hex)
                with self.assertRaises(Stale):
                    active_release(conn, target)
                retire(conn, token, "FAILED")
            held, release = Event(), Event()

            def pause(sql):
                if sql.startswith("CREATE TRANSIENT SCHEMA AIRLINE_DB.RELEASE_"):
                    held.set()
                    if not release.wait(15):
                        raise TimeoutError("Test publication was not released")

            token = claim(conn, target, uuid.uuid4().hex)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    publish, SQLFaultConnection(conn, pause), token, candidate, uuid.uuid4().hex
                )
                try:
                    self.assertTrue(held.wait(10))
                    cancel(canceller, token)
                finally:
                    release.set()
                with self.assertRaises(Stale):
                    future.result(timeout=90)
            retire(conn, token, "CANCELLED")
            with self.assertRaises(Stale):
                active_release(conn, target)

    def test_snapshot_independence_frozen_validation_and_actual_role_denials(self):
        from airline_warehouse.analytics import Filters, query_metrics
        from airline_warehouse.publication import active_release, claim, initialize, publish, retire
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        source = candidate["schema"]
        candidate["schema"] = "WORK_" + uuid.uuid4().hex[:24].upper()
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
            connect_as("reader") as reader,
        ):
            with builder.cursor() as cur:
                cur.execute(
                    f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{candidate['schema']} "
                    "DATA_RETENTION_TIME_IN_DAYS=1"
                )
                for table in ("FACT_FLIGHTS", "DIM_DATE", "DIM_AIRPORT", "DIM_CARRIER"):
                    cur.execute(
                        f"CREATE TRANSIENT TABLE AIRLINE_DB.{candidate['schema']}.{table} "
                        f"CLONE AIRLINE_DB.{source}.{table}"
                    )
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            initialize(conn, target)
            first = publish(
                conn, claim(conn, target, uuid.uuid4().hex), candidate, uuid.uuid4().hex
            )
            with builder.cursor() as cur:
                cur.execute(
                    f"UPDATE AIRLINE_DB.{candidate['schema']}.FACT_FLIGHTS SET \"ArrDelay\"='123'"
                )
            # Snapshot still contains the original values, despite deliberate source corruption.
            row = query_metrics(reader, first, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2)))[0]
            self.assertEqual(row["SIGNED_ARRIVAL_COUNT"], 5)
            self.assertAlmostEqual(row["SIGNED_MEAN"], 15.8)
            bad = claim(conn, target, uuid.uuid4().hex)
            with self.assertRaisesRegex(ValueError, "Frozen"):
                publish(conn, bad, candidate, uuid.uuid4().hex)
            retire(conn, bad, "FAILED")
            self.assertEqual(active_release(reader, target), first)
            for identity, sql in (
                (reader, f"SELECT * FROM AIRLINE_DB.{first['schema']}.FACT_FLIGHTS LIMIT 0"),
                (reader, "SELECT * FROM AIRLINE_DB.CONTROL.RUNS LIMIT 0"),
                (
                    reader,
                    f"UPDATE AIRLINE_DB.{first['schema']}.FACT_FLIGHTS "
                    "SET cancelled=cancelled WHERE 1=0",
                ),
                (
                    builder,
                    f"UPDATE AIRLINE_DB.{first['schema']}.FACT_FLIGHTS "
                    "SET cancelled=cancelled WHERE 1=0",
                ),
                (builder, "UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard=guard WHERE 1=0"),
                (
                    conn,
                    "UPDATE AIRLINE_DB.RAW.BTS_202501_EB0C52473E89616864F5287D54D2110E "
                    'SET "Cancelled"="Cancelled" WHERE 1=0',
                ),
            ):
                with identity.cursor() as cur:
                    with self.assertRaises(Exception) as error:
                        cur.execute(sql)
                    self.assertIn(
                        getattr(error.exception, "sqlstate", None), ("42501", "02000", "42S02")
                    )

    def test_pinned_reads_retention_expiration_and_cancelled_update(self):
        from airline_warehouse.analytics import Filters, query_metrics
        from airline_warehouse.publication import (
            Stale,
            active_release,
            cancel,
            claim,
            initialize,
            publish,
            retire,
            validate_reader_token,
        )
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
            connect_as("reader") as reader,
        ):
            initialize(conn, target)
            with self.assertRaises(Stale):
                active_release(reader, target)
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            first = publish(
                conn, claim(conn, target, uuid.uuid4().hex), candidate, uuid.uuid4().hex
            )
            pinned = active_release(reader, target)
            second = publish(
                conn, claim(conn, target, uuid.uuid4().hex), candidate, uuid.uuid4().hex
            )
            validate_reader_token(reader, pinned)
            self.assertEqual(pinned, first)
            self.assertEqual(active_release(reader, target), second)
            third = publish(
                conn, claim(conn, target, uuid.uuid4().hex), candidate, uuid.uuid4().hex
            )
            validate_reader_token(reader, pinned)  # retained even after leaving previous slot
            row = query_metrics(reader, pinned, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2)))[
                0
            ]
            self.assertEqual(row["ARRIVAL_NUMERATOR"], 4)
            # Fixture clock adjustment only, under the same lock-first discipline.
            with conn.cursor() as cur:
                cur.execute("BEGIN TRANSACTION")
                try:
                    cur.execute(
                        "UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard=guard+1 WHERE target=%s",
                        (target,),
                    )
                    cur.execute(
                        "UPDATE AIRLINE_DB.CONTROL.RELEASES SET "
                        "retired_until=DATEADD(hour,-1,CURRENT_TIMESTAMP()) "
                        "WHERE target=%s AND release_id=%s",
                        (target, first["release_id"]),
                    )
                    cur.execute("COMMIT")
                except BaseException:
                    cur.execute("ROLLBACK")
                    raise
            with self.assertRaises(Stale):
                validate_reader_token(reader, pinned)
            validate_reader_token(reader, second)  # previous retained regardless of clock
            cancelled = claim(conn, target, uuid.uuid4().hex)
            cancel(conn, cancelled)
            with self.assertRaises(Stale):
                publish(conn, cancelled, candidate, uuid.uuid4().hex)
            retire(conn, cancelled, "CANCELLED")
            self.assertEqual(active_release(reader, target), third)

    def test_real_competing_guard_lock_timeout_and_no_stale_takeover(self):
        from airline_warehouse.publication import Busy, claim, initialize, retire

        target = "test_" + uuid.uuid4().hex[:16]
        held, release = Event(), Event()

        def pause(sql):
            if sql.startswith("UPDATE AIRLINE_DB.CONTROL.TARGETS SET guard"):
                held.set()
                if not release.wait(15):
                    raise TimeoutError("Test guard was not released")

        with (
            connect_as("publisher") as first,
            connect_as("publisher") as second,
            live_budget(first, Path(os.environ["AIRLINE_BATCH_STATE"])),
        ):
            initialize(first, target)
            with second.cursor() as cur:
                cur.execute("ALTER SESSION SET LOCK_TIMEOUT=1")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    claim, SQLFaultConnection(first, pause), target, uuid.uuid4().hex
                )
                try:
                    self.assertTrue(held.wait(10))
                    with self.assertRaises(Exception) as error:
                        claim(second, target, uuid.uuid4().hex)
                    self.assertIn("lock", str(error.exception).lower())
                finally:
                    release.set()
                token = future.result(timeout=20)
            with self.assertRaises(Busy):
                claim(second, target, uuid.uuid4().hex)
            retire(first, token, "FAILED")

    def test_transaction_step_failures_roll_back_and_lost_commit_reconciles(self):
        from airline_warehouse.publication import (
            CommitUnknown,
            Stale,
            active_release,
            claim,
            initialize,
            publish,
            reconcile,
            retire,
        )
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
        ):
            initialize(conn, target)
            # Each claim transaction statement fails AFTER its actual server execution.
            for fail_at in range(1, 6):
                count = 0

                def fail(sql, fail_at=fail_at):
                    nonlocal count
                    if sql not in ("BEGIN TRANSACTION", "ROLLBACK"):
                        count += 1
                        if count == fail_at:
                            raise RuntimeError("Injected statement response failure")

                with self.assertRaises(RuntimeError):
                    claim(SQLFaultConnection(conn, fail), target, uuid.uuid4().hex)
                token = claim(conn, target, uuid.uuid4().hex)
                retire(conn, token, "FAILED")
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            token = claim(conn, target, uuid.uuid4().hex)
            release_id = uuid.uuid4().hex
            publishing = False

            def lose_commit(sql):
                nonlocal publishing
                if sql.startswith("INSERT INTO AIRLINE_DB.CONTROL.RELEASES"):
                    publishing = True
                if sql == "COMMIT" and publishing:
                    raise OSError("Injected lost COMMIT acknowledgment")

            with self.assertRaises(CommitUnknown):
                publish(SQLFaultConnection(conn, lose_commit), token, candidate, release_id)
            with connect_as("publisher") as fresh:
                descriptor = reconcile(fresh, token, release_id)
                self.assertEqual(active_release(fresh, target), descriptor)
                with self.assertRaises(Stale):
                    retire(fresh, token, "FAILED")

    def test_frozen_release_is_readable_and_failed_update_preserves_pointer(self):
        from airline_warehouse.analytics import Filters, query_metrics
        from airline_warehouse.publication import active_release, claim, initialize, publish, retire
        from airline_warehouse.warehouse import grant_candidate

        target = "test_" + uuid.uuid4().hex[:16]
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
            connect_as("builder") as builder,
        ):
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            initialize(conn, target)
            token = claim(conn, target, uuid.uuid4().hex)
            released = publish(conn, token, candidate, uuid.uuid4().hex)
            self.assertEqual(active_release(conn, target), released)
            with connect_as("reader") as reader:
                descriptor = active_release(reader, target)
                row = query_metrics(
                    reader, descriptor, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2))
                )[0]
                self.assertEqual(row["SCHEDULED_ROWS"], 9)
                self.assertEqual(row["ARRIVAL_NUMERATOR"], 4)
            failed = claim(conn, target, uuid.uuid4().hex)
            retire(conn, failed, "FAILED")
            self.assertEqual(active_release(conn, target), released)

    def test_claim_is_idempotent_and_competing_request_cannot_take_over(self):
        from airline_warehouse.publication import Busy, claim, initialize, retire

        target = "test_" + uuid.uuid4().hex[:16]
        with (
            connect_as("publisher") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])),
        ):
            initialize(conn, target)
            token = claim(conn, target, uuid.uuid4().hex)
            self.assertEqual(claim(conn, target, token["request_id"]), token)
            with self.assertRaises(Busy):
                claim(conn, target, uuid.uuid4().hex)
            retire(conn, token, "FAILED")  # synchronous test has no data-capable work
            next_token = claim(conn, target, uuid.uuid4().hex)
            self.assertGreater(next_token["fence"], token["fence"])
            retire(conn, next_token, "FAILED")

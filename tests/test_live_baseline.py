"""Explicit two-partition guard qualification before the full baseline is published."""

import json
import os
import unittest
import uuid
from pathlib import Path

from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.publication import active_release, claim, initialize, publish, retire
from airline_warehouse.warehouse import grant_candidate


@unittest.skipUnless(
    os.environ.get("AIRLINE_BASELINE_LIVE") == "funded-14",
    "Requires funded isolated two-month guard fixture",
)
class BaselinePartitionTests(unittest.TestCase):
    def test_reviewed_allocation_exception_requires_every_exact_source_identifier(self):
        c = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        sql = (Path(__file__).parents[1] / "dbt/tests/secondary_integrity.sql").read_text()
        sql = sql.replace("{{ ref('fact_flights') }}", "fixture")
        source = "68c5a96d28c6193a85e7257ba131faf0112b810c54e3a9fc38ff61cb66b5bfa0"
        fingerprint = "276f51920a74634e164decea6802afb1176382e87e28c3d5429ef66daa98b849"
        with (
            connect_as("builder") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            with DeadlineConnection(conn, remaining).cursor() as cur:
                for sha, ordinal, row_sha, expected in [
                    (source, 416811, fingerprint, 0),
                    ("0" * 64, 416811, fingerprint, 1),
                    (source, 416812, fingerprint, 1),
                    (source, 416811, "0" * 64, 1),
                ]:
                    with self.subTest(sha=sha, ordinal=ordinal, row_sha=row_sha):
                        cur.execute(
                            "WITH fixture AS (SELECT * REPLACE ("
                            '%s AS "SOURCE_SHA256", %s AS "SOURCE_ROW_NUMBER", '
                            '%s AS "SOURCE_ROW_SHA256", '
                            "231.0 AS arrival_delay, -5.0 AS departure_delay, "
                            "'0.00' AS \"CarrierDelay\", '0.00' AS \"WeatherDelay\", "
                            "'0.00' AS \"NASDelay\", '0.00' AS \"SecurityDelay\", "
                            "'0.00' AS \"LateAircraftDelay\", "
                            "0.0 AS carrier_minutes, 0.0 AS weather_minutes, "
                            "0.0 AS nas_minutes, 0.0 AS security_minutes, "
                            "0.0 AS late_aircraft_minutes, 0.0 AS reported_minutes, "
                            "231.0 AS unallocated_minutes, FALSE AS recovery_eligible, "
                            "NULL::DOUBLE AS signed_improvement, "
                            "FALSE AS recovered_below_threshold, "
                            "NULL::VARCHAR AS recovery_band) "
                            f"FROM AIRLINE_DB.{c['schema']}.FACT_FLIGHTS "
                            "WHERE category_complete LIMIT 1) "
                            "SELECT COUNT(*) FROM (" + sql + ")",
                            (sha, ordinal, row_sha),
                        )
                        self.assertEqual(cur.fetchone()[0], expected)

    def test_source_2400_is_retained_without_inventing_an_adjacent_calendar_date(self):
        import datetime as dt

        from airline_warehouse.analytics import Filters, query_metrics

        c = json.loads(Path(os.environ["AIRLINE_MIDNIGHT_CANDIDATE"]).read_text())
        with (
            connect_as("builder") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            conn = DeadlineConnection(conn, remaining)
            rows = query_metrics(
                conn, c, Filters(dt.date(2025, 2, 1), dt.date(2025, 2, 1)), "hour", development=True
            )
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT "CRSDepTime",flight_date,scheduled_local_hour '
                    f"FROM AIRLINE_DB.{c['schema']}.FACT_FLIGHTS WHERE \"CRSDepTime\"='2400'"
                )
                native = cur.fetchall()
        self.assertEqual(
            {row["SCHEDULED_LOCAL_HOUR"]: row["SCHEDULED_ROWS"] for row in rows}, {0: 1, 24: 1}
        )
        self.assertEqual(native, [("2400", dt.date(2025, 2, 1), 24)])

    def test_one_wrong_artifact_assignment_cannot_hide_behind_correct_global_counts(self):
        c = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        self.assertEqual(c["input_counts"], {"2025-01": 8, "2025-02": 2})
        target = "test_" + uuid.uuid4().hex[:16]
        budget = Path(os.environ["AIRLINE_BATCH_STATE"])
        with (
            connect_as("builder") as builder,
            connect_as("publisher") as publisher,
            live_budget(builder, budget) as remaining,
        ):
            builder, publisher = (DeadlineConnection(x, remaining) for x in (builder, publisher))
            grant_candidate(builder, c, "AIRLINE_PUBLISHER_ROLE")
            initialize(publisher, target)
            first = publish(
                publisher, claim(publisher, target, uuid.uuid4().hex), c, uuid.uuid4().hex
            )
            damaged = {**c, "schema": "WORK_" + uuid.uuid4().hex[:24].upper()}
            with builder.cursor() as cur:
                cur.execute(f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{damaged['schema']}")
                for table in c["tables"]:
                    cur.execute(
                        f"CREATE TRANSIENT TABLE AIRLINE_DB.{damaged['schema']}.{table} "
                        f"CLONE AIRLINE_DB.{c['schema']}.{table}"
                    )
                cur.execute(
                    f"UPDATE AIRLINE_DB.{damaged['schema']}.FACT_FLIGHTS "
                    "SET loaded_artifact_id=%s WHERE flight_key=("
                    f"SELECT MIN(flight_key) FROM AIRLINE_DB.{damaged['schema']}.FACT_FLIGHTS "
                    "WHERE flight_date='2025-02-01')",
                    (c["inputs"]["2025-01"],),
                )
            grant_candidate(builder, damaged, "AIRLINE_PUBLISHER_ROLE")
            token = claim(publisher, target, uuid.uuid4().hex)
            with self.assertRaisesRegex(ValueError, "per-month"):
                publish(publisher, token, damaged, uuid.uuid4().hex)
            retire(publisher, token, "FAILED")
            current = active_release(publisher, target)
        self.assertEqual(current, first)

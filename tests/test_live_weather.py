"""Funded fixed-pilot and focused real SQL weather boundary qualification."""

import datetime as dt
import json
import os
import unittest
from pathlib import Path

from airline_warehouse.analytics import Filters, query_weather
from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.weather import render_weather_sql, validate_frozen_weather


@unittest.skipUnless(
    os.environ.get("AIRLINE_WEATHER_LIVE") == "funded-12", "Requires explicit funded full pilot"
)
class WeatherSQLTests(unittest.TestCase):
    def test_required_weather_failure_preserves_complete_release(self):
        import uuid

        from airline_warehouse.publication import active_release, claim, initialize, publish, retire
        from airline_warehouse.warehouse import grant_candidate

        c = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        target = "test_" + uuid.uuid4().hex[:16]
        with (
            connect_as("builder") as builder,
            connect_as("publisher") as publisher,
            live_budget(builder, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
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
                    f"UPDATE AIRLINE_DB.{damaged['schema']}.DEN_WEATHER "
                    "SET temperature_value=999 WHERE temperature_match_status='matched'"
                )
            grant_candidate(builder, damaged, "AIRLINE_PUBLISHER_ROLE")
            token = claim(publisher, target, uuid.uuid4().hex)
            with self.assertRaisesRegex(ValueError, "weather"):
                publish(publisher, token, damaged, uuid.uuid4().hex)
            retire(publisher, token, "FAILED")
            actual = active_release(publisher, target)
        self.assertEqual(actual, first)
        with connect_as("reader") as reader:
            rows = query_weather(reader, first, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31)))
        self.assertEqual(sum(r["SCHEDULED_ROWS"] for r in rows["pilot_coverage"]), 24732 * 3)

    def test_independent_asof_age_boundaries_future_rejection_and_older_good_fallback(self):
        import uuid

        c = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        schema = "WORK_" + uuid.uuid4().hex[:24].upper()
        records = []
        for variable, stamp, value, status in (
            ("temperature", "14:00:00", 1, "accepted"),
            ("temperature", "15:00:00", None, "rejected_qc"),
            ("wind", "14:00:00", 5, "accepted"),
            ("wind", "15:00:00", 6, "accepted"),
            ("visibility", "13:59:59", 1000, "accepted"),
            ("visibility", "15:01:00", 2000, "accepted"),
        ):
            records.append(
                json.dumps(
                    dict(
                        station="72565003017",
                        variable=variable,
                        observed_at="2025-01-01T" + stamp,
                        value=value,
                        status=status,
                        provenance=[],
                        duplicate_count=1,
                    )
                )
            )
        with (
            connect_as("builder") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            with DeadlineConnection(conn, remaining).cursor() as cur:
                cur.execute(f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{schema}")
                cur.execute(
                    f"CREATE TRANSIENT TABLE AIRLINE_DB.{schema}.FACT_FLIGHTS AS "
                    f"SELECT * FROM AIRLINE_DB.{c['schema']}.FACT_FLIGHTS "
                    "WHERE origin_id=11292 AND flight_date='2025-01-01' "
                    "ORDER BY flight_key LIMIT 3"
                )
                cur.execute(f"UPDATE AIRLINE_DB.{schema}.FACT_FLIGHTS SET \"CRSDepTime\"='0800'")
                cur.execute(
                    f"UPDATE AIRLINE_DB.{schema}.FACT_FLIGHTS SET \"CRSDepTime\"='0801' "
                    f"WHERE flight_key=(SELECT MIN(flight_key) "
                    f"FROM AIRLINE_DB.{schema}.FACT_FLIGHTS)"
                )
                cur.execute(
                    f"UPDATE AIRLINE_DB.{schema}.FACT_FLIGHTS SET \"CRSDepTime\"='0600' "
                    f"WHERE flight_key=(SELECT MAX(flight_key) "
                    f"FROM AIRLINE_DB.{schema}.FACT_FLIGHTS)"
                )
                cur.execute(
                    f"CREATE VIEW AIRLINE_DB.{schema}.INPUT AS "
                    "SELECT column1 AS preserved_record FROM VALUES "
                    + ",".join(["(%s)"] * len(records)),
                    records,
                )
                # The input view is an explicit synthetic adapter, never accepted RAW.
                sql = render_weather_sql("weather_observations", schema).replace(
                    f"AIRLINE_DB.{schema}.WEATHER_OBSERVATIONS", f"AIRLINE_DB.{schema}.INPUT"
                )
                cur.execute(
                    f"CREATE TRANSIENT TABLE AIRLINE_DB.{schema}.WEATHER_OBSERVATIONS AS {sql}"
                )
                cur.execute(
                    f"CREATE TRANSIENT TABLE AIRLINE_DB.{schema}.DEN_WEATHER AS "
                    + render_weather_sql("den_weather", schema)
                )
                cur.execute(
                    f"SELECT source_clock,temperature_age_seconds,temperature_match_status,"
                    "temperature_older_good_fallback,wind_age_seconds,visibility_age_seconds,"
                    f"visibility_match_status FROM AIRLINE_DB.{schema}.DEN_WEATHER "
                    "ORDER BY source_clock"
                )
                rows = cur.fetchall()
        self.assertEqual(
            rows,
            [
                ("0600", None, "no_prior_accepted", False, None, None, "no_prior_accepted"),
                ("0800", 3600, "matched", True, 0, 3601, "stale"),
                ("0801", 3660, "stale", False, 60, 0, "matched"),
            ],
        )

    def test_full_pilot_all_rows_and_frozen_reconstruction(self):
        c = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("builder") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            bounded = DeadlineConnection(conn, remaining)
            validate_frozen_weather(bounded, c["schema"], c["weather"])
            result = query_weather(
                bounded, c, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31)), development=True
            )
        for v in ("temperature", "wind", "visibility"):
            rows = [r for r in result["pilot_coverage"] if r["VARIABLE"] == v]
            self.assertEqual(sum(r["SCHEDULED_ROWS"] for r in rows), 24732)
            self.assertEqual(sum(r["SCHEDULED_ROWS"] for r in rows if r["CANCELLED"] == 1), 313)
            self.assertGreaterEqual(sum(r["MATCHED_ROWS"] for r in rows) / 24732, 0.95)
            self.assertTrue(all(r["MAX_MATCHED_AGE_SECONDS"] <= 3600 for r in rows))

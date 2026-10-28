"""Explicit opt-in against a prebuilt synthetic candidate; never builds on discovery."""

import datetime as dt
import json
import os
import unittest
from pathlib import Path

from airline_warehouse.analytics import Filters, query_metrics
from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as


@unittest.skipUnless(
    os.environ.get("AIRLINE_ANALYTICS_LIVE") == "funded-05-10",
    "Requires explicit funded synthetic candidate",
)
class LiveMetricContractTests(unittest.TestCase):
    def test_server_timeout_decreases_and_expired_deadline_does_not_launch_sql(self):
        import time

        from airline_warehouse.deadlines import DeadlineConnection

        bounded = DeadlineConnection(self.conn, 5)
        with bounded.cursor() as cur:
            cur.execute("SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS' IN SESSION")
            first = int(cur.fetchone()[1])
            self.assertTrue(1 <= first <= 5)
            # A deterministic already-expired boundary never starts a server query.
            expired = DeadlineConnection(self.conn, 1, deadline=time.monotonic() - 1)
            with expired.cursor() as expired_cur:
                with self.assertRaises(TimeoutError):
                    expired_cur.execute("SELECT 1")

    @classmethod
    def setUpClass(cls):
        cls.descriptor = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        if cls.descriptor["expected_rows"] != 9:
            raise ValueError("This oracle requires the documented nine-row hand-authored fixture")
        cls.conn = connect_as("builder")
        cls.budget = live_budget(cls.conn, Path(os.environ["AIRLINE_BATCH_STATE"]))
        cls.budget.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.budget.__exit__(None, None, None)
        cls.conn.close()

    def read(self, scope, group="all", minimum=100):
        return query_metrics(
            self.conn, self.descriptor, scope, group, minimum=minimum, development=True
        )

    def test_signed_values_exact_quantiles_and_four_populations(self):
        first = self.read(Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 1)))[0]
        self.assertEqual(first["SCHEDULED_ROWS"], 5)
        self.assertAlmostEqual(float(first["ARRIVAL_RATE"]), 0.6, places=6)
        self.assertAlmostEqual(float(first["SIGNED_MEAN"]), 15.8, places=6)
        self.assertAlmostEqual(float(first["SIGNED_MEDIAN"]), 14, places=6)
        self.assertAlmostEqual(float(first["SIGNED_P90"]), 42, places=6)
        all_rows = self.read(Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2)))[0]
        self.assertEqual(all_rows["SCHEDULED_ROWS"], 9)
        self.assertEqual(all_rows["ARRIVAL_DENOMINATOR"], 6)
        self.assertEqual(all_rows["ARRIVAL_NUMERATOR"], 4)
        self.assertAlmostEqual(float(all_rows["ARRIVAL_RATE"]), 4 / 6, places=12)
        self.assertEqual(all_rows["CANCELLATION_NUMERATOR"], 1)
        self.assertEqual(all_rows["DIVERSION_NUMERATOR"], 1)
        self.assertEqual(all_rows["DEPARTURE_DENOMINATOR"], 7)
        self.assertEqual(all_rows["DEPARTURE_NUMERATOR"], 3)
        self.assertEqual(all_rows["SIGNED_ARRIVAL_COUNT"], 5)
        self.assertEqual(all_rows["UNKNOWN_ARRIVAL"], 1)
        self.assertEqual(all_rows["UNKNOWN_DEPARTURE"], 1)

    def test_ordered_routes_and_scheduled_not_actual_hour(self):
        scope = Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2))
        routes = self.read(scope, "route")
        self.assertEqual(
            {(r["ORIGIN_ID"], r["DESTINATION_ID"]): r["SCHEDULED_ROWS"] for r in routes},
            {(11292, 14771): 5, (14771, 11292): 4},
        )
        hours = self.read(Filters(scope.start, scope.start), "hour")
        self.assertEqual(
            [(r["SCHEDULED_LOCAL_HOUR"], r["SCHEDULED_ROWS"]) for r in hours], [(23, 5)]
        )

    def test_empty_scope_is_na_and_ranking_uses_each_eligible_population(self):
        scope = Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2), origin=99999)
        empty = self.read(scope)[0]
        self.assertEqual(empty["SCHEDULED_ROWS"], 0)
        for name in (
            "ARRIVAL_RATE",
            "CANCELLATION_RATE",
            "DIVERSION_RATE",
            "DEPARTURE_RATE",
            "SIGNED_P90",
        ):
            self.assertIsNone(empty[name])
        row = self.read(Filters(scope.start, scope.end), minimum=7)[0]
        self.assertFalse(row["ARRIVAL_RANKABLE"])
        self.assertTrue(row["SCHEDULE_RANKABLE"])
        self.assertTrue(row["DEPARTURE_RANKABLE"])

    @unittest.skipUnless(os.environ.get("AIRLINE_RANKING_CANDIDATE"), "Needs199-row ranking oracle")
    def test_99_and_100_eligible_observation_boundary(self):
        descriptor = json.loads(Path(os.environ["AIRLINE_RANKING_CANDIDATE"]).read_text())
        self.assertEqual(descriptor["expected_rows"], 199)
        rows = query_metrics(
            self.conn,
            descriptor,
            Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 1)),
            "carrier",
            minimum=100,
            development=True,
        )
        by_id = {r["MARKETING_CARRIER_ID"]: r for r in rows}
        self.assertEqual(by_id[19393]["ARRIVAL_DENOMINATOR"], 99)
        self.assertEqual(by_id[19805]["ARRIVAL_DENOMINATOR"], 100)
        self.assertFalse(by_id[19393]["ARRIVAL_RANKABLE"])
        self.assertTrue(by_id[19805]["ARRIVAL_RANKABLE"])

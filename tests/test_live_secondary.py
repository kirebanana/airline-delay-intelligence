"""Independent category/recovery oracle; explicit funded isolated candidate only."""

import datetime as dt
import json
import os
import unittest
from pathlib import Path

from airline_warehouse.analytics import Filters, query_secondary
from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection


@unittest.skipUnless(
    os.environ.get("AIRLINE_SECONDARY_LIVE") == "funded-11", "Requires explicit funded 11 fixture"
)
class SecondaryTests(unittest.TestCase):
    def test_frozen_secondary_corruption_retains_entire_prior_release(self):
        import uuid

        from airline_warehouse.publication import active_release, claim, initialize, publish, retire
        from airline_warehouse.warehouse import grant_candidate

        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        target = "test_" + uuid.uuid4().hex[:16]
        with (
            connect_as("builder") as builder,
            connect_as("publisher") as publisher,
            live_budget(builder, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            builder, publisher = (DeadlineConnection(c, remaining) for c in (builder, publisher))
            grant_candidate(builder, candidate, "AIRLINE_PUBLISHER_ROLE")
            initialize(publisher, target)
            first = publish(
                publisher, claim(publisher, target, uuid.uuid4().hex), candidate, uuid.uuid4().hex
            )
            damaged = {**candidate, "schema": "WORK_" + uuid.uuid4().hex[:24].upper()}
            with builder.cursor() as cur:
                cur.execute(f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{damaged['schema']}")
                for table in candidate["tables"]:
                    cur.execute(
                        f"CREATE TRANSIENT TABLE AIRLINE_DB.{damaged['schema']}.{table} "
                        f"CLONE AIRLINE_DB.{candidate['schema']}.{table}"
                    )
                cur.execute(
                    f"UPDATE AIRLINE_DB.{damaged['schema']}.FACT_FLIGHTS "
                    "SET signed_improvement=999 WHERE recovery_eligible"
                )
            grant_candidate(builder, damaged, "AIRLINE_PUBLISHER_ROLE")
            token = claim(publisher, target, uuid.uuid4().hex)
            with self.assertRaisesRegex(ValueError, "category/recovery"):
                publish(publisher, token, damaged, uuid.uuid4().hex)
            retire(publisher, token, "FAILED")
            actual = active_release(publisher, target)
        self.assertEqual(actual, first)
        with connect_as("reader") as reader:
            result = query_secondary(
                reader, first, Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31))
            )
        self.assertEqual(result["summary"]["RECOVERY_ELIGIBLE"], 4)

    def test_compatible_category_subset_overlap_and_signed_recovery(self):
        candidate = json.loads(Path(os.environ["AIRLINE_TEST_CANDIDATE"]).read_text())
        with (
            connect_as("builder") as conn,
            live_budget(conn, Path(os.environ["AIRLINE_BATCH_STATE"])) as remaining,
        ):
            result = query_secondary(
                DeadlineConnection(conn, remaining),
                candidate,
                Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31)),
                development=True,
            )
            empty = query_secondary(
                DeadlineConnection(conn, remaining),
                candidate,
                Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31), origin=99999),
                development=True,
            )
        if result:
            s = result["summary"]
            self.assertEqual(s["SCHEDULED_ROWS"], 8)
            self.assertEqual(s["CATEGORY_ELIGIBLE"], 3)
            self.assertEqual(s["CATEGORY_COMPLETE"], 2)
            self.assertEqual(s["MISSING_CATEGORY_ROWS"], 1)
            self.assertEqual(s["RECOVERY_ELIGIBLE"], 4)
            # Improvements 6,15,0,-5 => mean4, median3, exact p90=12.3.
            self.assertAlmostEqual(s["IMPROVEMENT_MEAN"], 4)
            self.assertAlmostEqual(s["IMPROVEMENT_MEDIAN"], 3)
            self.assertAlmostEqual(s["IMPROVEMENT_P90"], 12.3)
            self.assertEqual(s["RECOVERED"], 1)
            self.assertEqual(s["RECOVERY_SHARE"], 0.25)
            categories = {r["CATEGORY"]: r for r in result["categories"]}
            self.assertEqual(categories["Carrier"]["REPORTED_MINUTES"], 20)
            self.assertEqual(categories["Carrier"]["AFFECTED_ROWS"], 2)
            self.assertEqual(categories["NAS"]["AFFECTED_ROWS"], 2)
            self.assertAlmostEqual(categories["Carrier"]["MINUTE_SHARE"], 20 / 35)
            self.assertEqual(sum(r["CANCELLED_ROWS"] for r in result["cancellations"]), 1)
            self.assertEqual(
                result["cancellations"][0]["CANCELLATION_REASON"], "Unknown / unrecognized"
            )
            self.assertIsNone(empty["summary"]["RECOVERY_SHARE"])
            self.assertIsNone(empty["categories"][0]["MINUTE_SHARE"])

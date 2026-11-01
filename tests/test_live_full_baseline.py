"""Explicit final-scale failure preservation; never mutate accepted source/release rows."""

import datetime as dt
import json
import os
import unittest
import uuid
from pathlib import Path

from airline_warehouse.analytics import Filters, query_metrics
from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.publication import active_release, claim, publish, retire
from airline_warehouse.refresh import refresh
from airline_warehouse.warehouse import BASELINE_MONTHS, grant_candidate


@unittest.skipUnless(
    os.environ.get("AIRLINE_FULL_BASELINE_LIVE") == "funded-14-final",
    "Requires the independently qualified complete release and exact source selection",
)
class CompleteBaselineFailureTests(unittest.TestCase):
    def test_corrupt_secondary_update_retains_the_complete_release_and_weather(self):
        root = Path(os.environ["AIRLINE_BASELINE_EVIDENCE"]).resolve()
        candidate = json.loads((root / "release-36/candidate-reference.json").read_text())
        self.assertEqual(set(candidate["inputs"]), BASELINE_MONTHS)
        self.assertEqual(candidate["expected_rows"], 22562477)
        selected = json.loads((root / "selected.json").read_text())
        artifacts = [Path(item["artifact"]) for _, item in sorted(selected.items())]
        budget = root.parent / "budget.json"
        directory = root / ("failed-full-update-" + uuid.uuid4().hex[:16])
        directory.mkdir()
        damaged = {**candidate, "schema": "WORK_" + uuid.uuid4().hex[:24].upper()}
        with (
            connect_as("builder") as builder,
            connect_as("publisher") as publisher,
            live_budget(builder, budget) as remaining,
        ):
            builder, publisher = (DeadlineConnection(c, remaining) for c in (builder, publisher))
            before = active_release(publisher, "january")
            self.assertEqual(before["inputs"], candidate["inputs"])
            self.assertEqual(before["weather"], candidate["weather"])
            with builder.cursor() as cur:
                cur.execute(f"CREATE TRANSIENT SCHEMA AIRLINE_DB.{damaged['schema']}")
                for table in candidate["tables"]:
                    cur.execute(
                        f"CREATE TRANSIENT TABLE AIRLINE_DB.{damaged['schema']}.{table} "
                        f"CLONE AIRLINE_DB.{candidate['schema']}.{table}"
                    )
                cur.execute(
                    f"UPDATE AIRLINE_DB.{damaged['schema']}.FACT_FLIGHTS "
                    "SET signed_improvement=-999999 WHERE flight_key=("
                    f"SELECT MIN(flight_key) FROM AIRLINE_DB.{damaged['schema']}.FACT_FLIGHTS "
                    "WHERE recovery_eligible)"
                )
                self.assertEqual(cur.rowcount, 1)
            grant_candidate(builder, damaged, "AIRLINE_PUBLISHER_ROLE")
        bad_path = directory / "damaged-candidate.json"
        bad_path.write_text(json.dumps(damaged, indent=2) + "\n")
        reused = refresh(
            artifacts,
            directory / "reuse-attempt",
            budget,
            "january",
            uuid.uuid4().hex,
            stage="publish",
            candidate_path=bad_path,
            weather_path=root.parent / "weather-artifact-v2",
        )
        # Unchanged declared dependencies safely reuse the accepted release; they
        # cannot force publication of arbitrary new work. Exercise the frozen
        # boundary independently, as the smaller publication fixtures do.
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["descriptor"], before)
        with connect_as("publisher") as publisher, live_budget(publisher, budget) as remaining:
            publisher = DeadlineConnection(publisher, remaining)
            request, release = uuid.uuid4().hex, uuid.uuid4().hex
            (directory / "publication-intent.json").write_text(
                json.dumps(dict(target="january", request_id=request, release_id=release)) + "\n"
            )
            token = claim(publisher, "january", request)
            with self.assertRaisesRegex(ValueError, "category/recovery"):
                publish(
                    publisher,
                    token,
                    damaged,
                    release,
                    evidence_path=directory / "publication-queries.jsonl",
                )
            retire(publisher, token, "FAILED")
        with (
            connect_as("publisher") as publisher,
            connect_as("reader") as reader,
            live_budget(publisher, budget) as remaining,
        ):
            after = active_release(DeadlineConnection(publisher, remaining), "january")
            self.assertEqual(after, before)
            metrics = query_metrics(
                DeadlineConnection(reader, remaining),
                after,
                Filters(dt.date(2023, 1, 1), dt.date(2025, 12, 31)),
            )[0]
            self.assertEqual(metrics["SCHEDULED_ROWS"], 22562477)
        evidence = dict(
            retained_descriptor=after,
            retained_metrics=metrics,
            attempt=str(directory),
            unchanged_dependencies_reuse_safe=True,
            corruption="one derived recovery value in an isolated clone",
            accepted_source_and_release_unchanged=True,
        )
        (root / "full-failure-evidence.json").write_text(
            json.dumps(evidence, indent=2, default=str) + "\n"
        )

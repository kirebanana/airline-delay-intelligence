"""Real refresh/replay/correction acceptance with independently worked nine-row oracles."""

import datetime as dt
import gzip
import hashlib
import json
import os
import unittest
import uuid
from pathlib import Path

from airline_warehouse.analytics import Filters, query_metrics
from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as


@unittest.skipUnless(
    os.environ.get("AIRLINE_ANALYTICS_LIVE") == "funded-05-10",
    "Requires explicit funded local refresh qualification",
)
class RefreshTests(unittest.TestCase):
    def test_replay_correction_clean_rebuild_and_changed_preparation(self):
        from analytics_fixtures import fixture, load_fixture

        from airline_warehouse.load import read_artifact
        from airline_warehouse.publication import active_release, initialize
        from airline_warehouse.refresh import refresh

        root = Path(os.environ["AIRLINE_TEST_CANDIDATE"]).resolve().parents[1]
        base = root / "metric-fixture"
        directory = root / ("refresh-test-" + uuid.uuid4().hex[:16])
        directory.mkdir()
        ledger = Path(os.environ["AIRLINE_BATCH_STATE"])
        target, clean = ("test_" + uuid.uuid4().hex[:16] for _ in range(2))
        with connect_as("publisher") as conn, live_budget(conn, ledger):
            initialize(conn, target)
            initialize(conn, clean)
        request_id = uuid.uuid4().hex
        first = refresh(
            [base],
            directory / "first",
            ledger,
            target,
            request_id,
            stage="publish",
            candidate_path=Path(os.environ["AIRLINE_TEST_CANDIDATE"]),
        )
        repeated = refresh([base], directory / "duplicate", ledger, target, request_id)
        replay = refresh([base], directory / "replay", ledger, target, uuid.uuid4().hex)
        self.assertEqual(first["descriptor"], repeated["descriptor"])
        self.assertEqual(first["descriptor"], replay["descriptor"])
        self.assertTrue(replay["reused"])
        unknown_path = directory / "unknown-outcome"
        unknown = fixture(unknown_path, "unknown")
        with connect_as("builder") as conn, live_budget(conn, ledger):
            load_fixture(conn, unknown_path, unknown)
        with self.assertRaises(ValueError):
            refresh(
                [unknown_path],
                directory / "failed-update",
                ledger,
                target,
                uuid.uuid4().hex,
                stage="build",
            )
        with connect_as("publisher") as conn, live_budget(conn, ledger):
            self.assertEqual(active_release(conn, target), first["descriptor"])
        correction_path = directory / "controlled-correction"
        correction = fixture(correction_path, "correction")
        with connect_as("builder") as conn, live_budget(conn, ledger):
            load_fixture(conn, correction_path, correction)
        corrected = refresh(
            [correction_path], directory / "corrected", ledger, target, uuid.uuid4().hex
        )
        rebuilt = refresh(
            [correction_path],
            directory / "clean-rebuild",
            ledger,
            clean,
            uuid.uuid4().hex,
            stage="build",
        )
        with (
            connect_as("reader") as reader,
            connect_as("publisher") as publisher,
            live_budget(publisher, ledger),
        ):
            rows = []
            for result in (corrected, rebuilt):
                row = query_metrics(
                    reader, result["descriptor"], Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2))
                )[0]
                rows.append(row)
                self.assertEqual(row["SCHEDULED_ROWS"], 9)
                self.assertEqual(row["ARRIVAL_NUMERATOR"], 3)
                self.assertEqual(row["ARRIVAL_DENOMINATOR"], 6)
                self.assertEqual(row["CANCELLATION_NUMERATOR"], 1)
                self.assertEqual(row["DIVERSION_NUMERATOR"], 1)
                self.assertEqual(row["DEPARTURE_NUMERATOR"], 4)
                self.assertEqual(row["SIGNED_ARRIVAL_COUNT"], 6)
                self.assertAlmostEqual(row["SIGNED_MEAN"], 14)
                self.assertAlmostEqual(row["SIGNED_MEDIAN"], 14.5)
                self.assertAlmostEqual(row["SIGNED_P90"], 37.5)
            self.assertEqual(rows[0], rows[1])
        # Same ZIP and logical values, independently repacked prepared bytes: new load identity.
        repacked = directory / "repacked"
        repacked.mkdir()
        original = read_artifact(base)
        data = gzip.decompress((base / "prepared.csv.gz").read_bytes())
        payload = gzip.compress(data, compresslevel=1, mtime=0)
        (repacked / "prepared.csv.gz").write_bytes(payload)
        alternate = {**original, "prepared_sha256": hashlib.sha256(payload).hexdigest()}
        alternate["loaded_artifact_id"] = hashlib.sha256(
            f"{alternate['source_sha256']}:{alternate['preparation_contract']}:"
            f"{alternate['prepared_sha256']}".encode("ascii")
        ).hexdigest()
        (repacked / "manifest.json").write_text(json.dumps(alternate, indent=2) + "\n")
        self.assertEqual(read_artifact(repacked)["source_sha256"], original["source_sha256"])
        self.assertNotEqual(alternate["loaded_artifact_id"], original["loaded_artifact_id"])
        with connect_as("builder") as conn, live_budget(conn, ledger):
            load_fixture(conn, repacked, alternate)
        reprocessed = refresh(
            [repacked], directory / "reprocessed", ledger, target, uuid.uuid4().hex
        )
        self.assertEqual(
            reprocessed["descriptor"]["inputs"], {"2025-01": alternate["loaded_artifact_id"]}
        )
        with (
            connect_as("reader") as reader,
            connect_as("publisher") as publisher,
            live_budget(publisher, ledger),
        ):
            row = query_metrics(
                reader, reprocessed["descriptor"], Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 2))
            )[0]
            self.assertEqual(row["SCHEDULED_ROWS"], 9)
            self.assertEqual(row["ARRIVAL_NUMERATOR"], 4)
            self.assertAlmostEqual(row["SIGNED_MEAN"], 15.8)
            self.assertEqual(active_release(reader, target), reprocessed["descriptor"])
        (directory / "acceptance.json").write_text(
            json.dumps(
                {
                    "replay_reused": True,
                    "controlled_correction_not_official": True,
                    "clean_rebuild_matches": True,
                    "changed_preparation_distinct_load": True,
                    "corrected": corrected["descriptor"],
                    "reprocessed": reprocessed["descriptor"],
                },
                indent=2,
            )
            + "\n"
        )

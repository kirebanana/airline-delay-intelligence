import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from test_load import manifest

from airline_warehouse.budget import live_budget
from airline_warehouse.warehouse import candidate_plan


class WarehouseContractTests(unittest.TestCase):
    def test_metadata_preflight_cannot_extend_the_whole_run_deadline(self):
        clock = [100]

        class MetadataDriver:
            @contextmanager
            def cursor(self):
                yield self

            def execute(self, sql, **kwargs):
                if "RESOURCE MONITORS" in sql:
                    self.row = {
                        "name": "AIRLINE_BUDGET",
                        "level": "ACCOUNT",
                        "credit_quota": "5",
                        "used_credits": "0",
                        "remaining_credits": "5",
                        "suspend_immediately_at": "100%",
                    }
                elif "SHOW WAREHOUSES" in sql:
                    self.row = {
                        "size": "X-Small",
                        "enable_query_acceleration": "false",
                        "auto_suspend": 60,
                    }
                    clock[0] = 125
                else:
                    return
                self.description = [(n,) for n in self.row]

            def fetchall(self):
                return [tuple(self.row.values())]

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("airline_warehouse.budget.time.monotonic", side_effect=lambda: clock[0]),
        ):
            path = Path(tmp) / "budget.json"
            with self.assertRaises(TimeoutError):
                with live_budget(MetadataDriver(), path, deadline=125):
                    self.fail("Expired preflight must not authorize data work")

    def test_two_local_processes_cannot_spend_the_same_budget_concurrently(self):
        import fcntl

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.json"
            with Path(str(path) + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "already active"):
                    with live_budget(None, path):
                        self.fail("Concurrent budget admission")

    def test_unknown_or_corrupt_prior_work_refuses_live_admission_before_connection_access(self):
        for update in (
            {"recovery_required": True},
            {"operation_active": True},
            {"elapsed_seconds": -1},
        ):
            with self.subTest(update=update), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "budget.json"
                path.write_text(
                    json.dumps(
                        {
                            "baseline_credits": "0.12",
                            "elapsed_seconds": 1,
                            "operations": [],
                            **update,
                        }
                    )
                )
                with self.assertRaises(ValueError):
                    with live_budget(None, path):
                        self.fail("Must not admit live work")

    def test_selected_month_contributes_once_and_preserves_artifact_identity(self):
        m = manifest()
        plan = candidate_plan([m], "WORK_" + "A" * 24)
        self.assertEqual(plan["expected_rows"], 599013)
        self.assertEqual(plan["inputs"]["2025-01"], m["loaded_artifact_id"])
        self.assertEqual(plan["input_counts"], {"2025-01": m["rows"]})
        self.assertEqual(plan["input_sources"], {"2025-01": m["source_sha256"]})
        with self.assertRaisesRegex(ValueError, "one.*month"):
            candidate_plan([m, m], "WORK_" + "A" * 24)
        with self.assertRaises(ValueError):
            candidate_plan([m], "RAW")

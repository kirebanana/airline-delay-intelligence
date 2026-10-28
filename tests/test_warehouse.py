import json
import tempfile
import unittest
from pathlib import Path

from test_load import manifest

from airline_warehouse.budget import live_budget
from airline_warehouse.warehouse import candidate_plan


class WarehouseContractTests(unittest.TestCase):
    def test_unknown_or_corrupt_prior_work_refuses_live_admission_before_connection_access(self):
        for update in ({"recovery_required": True}, {"elapsed_seconds": -1}):
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
        with self.assertRaisesRegex(ValueError, "one.*month"):
            candidate_plan([m, m], "WORK_" + "A" * 24)
        with self.assertRaises(ValueError):
            candidate_plan([m], "RAW")

import json
import tempfile
import unittest
from pathlib import Path


class RefreshRequestTests(unittest.TestCase):
    def test_incompatible_processing_or_preparation_never_enters_live_refresh(self):
        from test_prepare import archive

        from airline_warehouse.prepare import prepare
        from airline_warehouse.refresh import refresh

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive(root / "source.zip", [{}])
            prepare(root / "source.zip", root / "artifact", "2025-01", synthetic=True)
            candidate = root / "candidate.json"
            candidate.write_text(
                json.dumps(
                    {
                        "sealed": True,
                        "schema": "WORK_" + "A" * 24,
                        "processing_contract": "obsolete",
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "incompatible"):
                refresh(
                    [root / "artifact"],
                    root / "attempt",
                    root / "budget.json",
                    "january",
                    "a" * 32,
                    stage="publish",
                    candidate_path=candidate,
                )
            self.assertFalse((root / "attempt").exists())
            manifest_path = root / "artifact/manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["preparation_contract"] = "unsupported-preparation-v2"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                refresh(
                    [root / "artifact"], root / "attempt", root / "budget.json", "january", "b" * 32
                )
            self.assertFalse((root / "attempt").exists())

    def test_publish_rerun_refuses_missing_dependency_without_connecting(self):
        from airline_warehouse.refresh import refresh

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "candidate dependency"):
                refresh(
                    [], root / "attempt", root / "budget.json", "january", "a" * 32, stage="publish"
                )
            self.assertFalse((root / "attempt").exists())

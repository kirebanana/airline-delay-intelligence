import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from airline_warehouse.execution import WorkJournal, producer_lock, run_dbt_child
from airline_warehouse.recovery import recover_local


class AttendedRecoveryTests(unittest.TestCase):
    def test_child_process_group_is_finite_without_claiming_sql_termination(self):
        import os
        import sys
        import time

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            journal = WorkJournal(output / "work.jsonl")
            with producer_lock(journal.path):
                with self.assertRaises(TimeoutError):
                    run_dbt_child(
                        [sys.executable, "-c", "import time; time.sleep(100)"],
                        os.environ.copy(),
                        output,
                        time.monotonic() + 0.2,
                        journal,
                    )
            events = [json.loads(line) for line in journal.path.read_text().splitlines()]
            terminal = [e for e in events if e["event"] == "child_terminal"]
            self.assertEqual(len(terminal), 1)
            self.assertLess(terminal[0]["returncode"], 0)
            with producer_lock(journal.path, recovery=True):
                pass

    def test_unknown_query_status_never_clears_matching_uncertainty(self):
        class Driver:
            @contextmanager
            def cursor(self):
                yield self

            def execute(self, *args, **kwargs):
                pass

            def fetchone(self):
                return ("session [123] terminated.",)

            def get_query_status(self, query_id):
                from types import SimpleNamespace

                return SimpleNamespace(name="NO_DATA")

        @contextmanager
        def factory(*args, **kwargs):
            yield Driver()

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "intent.json").write_text('{"request_id":"fixture"}')
            journal = WorkJournal(output / "work.jsonl")
            journal.append("session", session_id=123, identity="builder")
            journal.append("query_result", session_id=123, query_id="unknown")
            budget = output / "budget.json"
            original = dict(recovery_required=True, recovery_work="fixture", elapsed_seconds=17)
            budget.write_text(json.dumps(original))
            with patch("airline_warehouse.recovery.connect_as", factory):
                with self.assertRaisesRegex(ValueError, "not proven"):
                    recover_local(output, budget)
            self.assertEqual(json.loads(budget.read_text()), original)

    def test_live_local_producer_prevents_recovery_before_any_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            journal = WorkJournal(output / "work.jsonl")
            journal.append("producer", identity="builder")
            budget = output / "budget.json"
            budget.write_text(json.dumps({"operation_active": True, "elapsed_seconds": 1}))
            with producer_lock(output / "work.jsonl"):
                with self.assertRaisesRegex(ValueError, "producer"):
                    recover_local(output, budget)
            self.assertTrue(json.loads(budget.read_text())["operation_active"])

    def test_missing_durable_intent_refuses_recovery_without_resetting_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            budget = output / "budget.json"
            budget.write_text('{"recovery_required":true,"elapsed_seconds":123}')
            with self.assertRaisesRegex(ValueError, "intent"):
                recover_local(output, budget)
            self.assertEqual(json.loads(budget.read_text())["elapsed_seconds"], 123)
            self.assertTrue(json.loads(budget.read_text())["recovery_required"])

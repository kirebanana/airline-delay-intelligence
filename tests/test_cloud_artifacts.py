import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from airline_warehouse.cloud_artifacts import ReportStore


class CloudArtifactsTests(unittest.TestCase):
    def test_large_candidate_payload_is_external_not_a_control_report(self):
        client = Mock()
        store = ReportStore(client, "warehouse", "a" * 32)
        payload = {"inputs": "x" * 20000}
        with self.assertRaises(ValueError):
            store.write("warehouse-report.json", payload)
        reference = store.write_payload("candidate-payload.json", payload)
        client.get_object.return_value = {
            "Body": io.BytesIO(client.put_object.call_args.kwargs["Body"])
        }
        self.assertEqual(store.read_payload(reference), payload)
        with self.assertRaises(ValueError):
            store.write_payload("warehouse-report.json", payload)

    def test_checked_small_report_roundtrip_rejects_corruption_and_scope_escape(self):
        client = Mock()
        store = ReportStore(client, "warehouse", "a" * 32)
        value = {"status": "SEALED", "rows": 2}
        reference = store.write("candidate.json", value)
        written = client.put_object.call_args.kwargs
        self.assertEqual(written["Key"], "reports/build/" + "a" * 32 + "/candidate.json")
        self.assertEqual(written["IfNoneMatch"], "*")
        self.assertEqual(reference["sha256"], hashlib.sha256(written["Body"]).hexdigest())
        client.get_object.return_value = {"Body": io.BytesIO(written["Body"])}
        self.assertEqual(store.read(reference), value)
        client.get_object.return_value = {"Body": io.BytesIO(b"corrupt")}
        with self.assertRaises(ValueError):
            store.read(reference)
        with self.assertRaises(ValueError):
            store.write("../state.json", {})
        with self.assertRaises(ValueError):
            store.read({"key": "reports/build/other/candidate.json", "sha256": "f" * 64})

    def test_durable_query_intent_precedes_driver_and_unknown_ack_leaves_intent(self):
        client = Mock()
        store = ReportStore(client, "warehouse", "a" * 32)
        with tempfile.TemporaryDirectory() as tmp:
            journal = store.journal(Path(tmp) / "work.jsonl")
            connection = Mock(session_id=42)
            journal.session(connection, "builder")
            cursor = Mock(sfqid=None)

            def driver(sql):
                events = [
                    json.loads(call.kwargs["Body"]) for call in client.put_object.call_args_list
                ]
                self.assertEqual(events[-1]["event"], "query_intent")
                raise RuntimeError("lost acknowledgement")

            with self.assertRaises(RuntimeError):
                journal.execute(driver, cursor, 42, "SELECT 1")
            events = [json.loads(call.kwargs["Body"]) for call in client.put_object.call_args_list]
            self.assertEqual(events[-1]["event"], "query_result")
            self.assertFalse(events[-1]["returned"])
            self.assertNotIn("SELECT 1", json.dumps(events))

    def test_failed_durable_intent_never_submits_query(self):
        client = Mock()
        client.put_object.side_effect = RuntimeError("lost report acknowledgement")
        journal = ReportStore(client, "warehouse", "a" * 32).journal(Path("unused.jsonl"))
        driver = Mock()
        with self.assertRaises(RuntimeError):
            journal.execute(driver, Mock(sfqid=None), 42, "SELECT 1")
        driver.assert_not_called()

    def test_durable_journal_latency_cannot_submit_after_absolute_sql_deadline(self):
        clock = [8]
        client = Mock()

        def write(**kwargs):
            if json.loads(kwargs["Body"])["event"] == "query_intent":
                clock[0] = 11

        client.put_object.side_effect = write
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("airline_warehouse.cloud_artifacts.time.monotonic", side_effect=lambda: clock[0]),
        ):
            journal = ReportStore(client, "warehouse", "a" * 32).journal(
                Path(tmp) / "work.jsonl", deadline=10
            )
            driver = Mock()
            with self.assertRaises(TimeoutError):
                journal.execute(driver, Mock(sfqid=None), 42, "SELECT 1", timeout=2)
            driver.assert_not_called()

    def test_journal_latency_clamps_server_and_client_limits_without_raising_them(self):
        clock = [10]
        client = Mock()

        def write(**kwargs):
            if json.loads(kwargs["Body"])["event"] == "query_intent":
                clock[0] = 17

        client.put_object.side_effect = write
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("airline_warehouse.cloud_artifacts.time.monotonic", side_effect=lambda: clock[0]),
        ):
            journal = ReportStore(client, "warehouse", "a" * 32).journal(
                Path(tmp) / "work.jsonl", deadline=20
            )
            driver = Mock()
            journal.execute(
                driver,
                Mock(sfqid=None),
                42,
                "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=10, "
                "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=2, LOCK_TIMEOUT=1",
                timeout=10,
                _statement_params={
                    "STATEMENT_TIMEOUT_IN_SECONDS": 10,
                    "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 2,
                    "LOCK_TIMEOUT": 1,
                    "QUERY_TAG": "airline:test",
                },
            )
            sql = driver.call_args.args[0]
            self.assertIn("STATEMENT_TIMEOUT_IN_SECONDS=3", sql)
            self.assertIn("STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=2", sql)
            self.assertIn("LOCK_TIMEOUT=1", sql)
            self.assertEqual(
                driver.call_args.kwargs,
                {
                    "timeout": 3,
                    "_statement_params": {
                        "STATEMENT_TIMEOUT_IN_SECONDS": 3,
                        "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 2,
                        "LOCK_TIMEOUT": 1,
                        "QUERY_TAG": "airline:test",
                    },
                },
            )

    def test_expired_journal_still_allows_only_bounded_rollback_cleanup(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("airline_warehouse.cloud_artifacts.time.monotonic", return_value=11),
        ):
            journal = ReportStore(Mock(), "warehouse", "a" * 32).journal(
                Path(tmp) / "work.jsonl", deadline=10
            )
            driver = Mock()
            journal.execute(driver, Mock(sfqid=None), 42, "ROLLBACK", timeout=5)
            self.assertEqual(driver.call_args.args, ("ROLLBACK",))
            self.assertEqual(driver.call_args.kwargs["timeout"], 5)
            self.assertEqual(driver.call_args.kwargs["_statement_params"]["LOCK_TIMEOUT"], 5)
            with self.assertRaises(TimeoutError):
                journal.execute(driver, Mock(sfqid=None), 42, "COMMIT", timeout=5)
            self.assertEqual(driver.call_count, 1)

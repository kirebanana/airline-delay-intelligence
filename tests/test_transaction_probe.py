import time
import unittest
from unittest.mock import MagicMock, Mock

from airline_warehouse.transaction_probe import submit_probe, validate_request


class TransactionProbeTests(unittest.TestCase):
    def test_probe_has_only_fixed_bounded_sql_and_never_commits_its_guard_write(self):
        conn = MagicMock(session_id=42)
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (7,)
        cursor.rowcount = 1
        cursor.sfqid = "query-id"
        journal = Mock()
        journal.session.return_value = 42
        journal.execute.side_effect = lambda execute, cur, sid, sql, *args, **kw: execute(
            sql, *args, **kw
        )
        token = self.request()["authority"]
        evidence = submit_probe(conn, journal, token, time.monotonic() + 180)
        self.assertEqual(evidence["guard_before_uncommitted_write"], 7)
        commands = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("BEGIN TRANSACTION", commands)
        self.assertNotIn("COMMIT", commands)
        self.assertNotIn("ROLLBACK", commands)
        cursor.execute_async.assert_called_once()
        self.assertEqual(cursor.execute_async.call_args.args[0], "SELECT SYSTEM$WAIT(120)")
        self.assertEqual(
            cursor.execute_async.call_args.kwargs["_statement_params"][
                "STATEMENT_TIMEOUT_IN_SECONDS"
            ],
            120,
        )

    def request(self):
        rid, target = "a" * 32, "test_" + "b" * 16
        return {
            "request_id": rid,
            "target": target,
            "deadline_epoch": 200,
            "task_definition_arn": (
                "arn:aws:ecs:us-east-2:336805808138:task-definition/"
                "airline-transaction-qualification:1"
            ),
            "budget": {"recovery_reserve_credits": "0.5"},
            "authority": {
                "target": target,
                "request_id": rid,
                "attempt": rid,
                "fence": 1,
                "status": "RUNNING",
            },
        }

    def test_explicit_exact_test_generation_and_short_deadline_are_required(self):
        request = self.request()
        self.assertEqual(validate_request(request, 100), request)
        for update in (
            {"target": "january"},
            {"deadline_epoch": 400},
            {"sql": "arbitrary"},
            {"authority": {}},
            {"budget": {"recovery_reserve_credits": "0"}},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_request({**request, **update}, 100)

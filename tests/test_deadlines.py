import unittest
from unittest.mock import patch

from airline_warehouse.deadlines import execute_bounded


class DeadlineTests(unittest.TestCase):
    def test_expired_deadline_refuses_sql_and_static_limits_cannot_extend_remaining_time(self):
        calls = []

        def driver(sql, **kwargs):
            calls.append((sql, kwargs))

        with patch("airline_warehouse.deadlines.time.monotonic", return_value=100):
            with self.assertRaises(TimeoutError):
                execute_bounded(driver, 100, "SELECT 1")
            self.assertEqual(calls, [])
            execute_bounded(driver, 125, "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=600")
            self.assertIn("STATEMENT_TIMEOUT_IN_SECONDS=25", calls[-1][0])
            self.assertEqual(calls[-1][1]["timeout"], 25)

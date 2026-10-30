import unittest
from unittest.mock import patch

from airline_warehouse.deadlines import DeadlineConnection, execute_bounded


class DeadlineTests(unittest.TestCase):
    def test_workload_carries_fresh_server_and_client_limits(self):
        clock = [100]
        calls = []

        def driver(sql, **kwargs):
            calls.append((sql, kwargs))
            clock[0] = 120

        with patch("airline_warehouse.deadlines.time.monotonic", side_effect=lambda: clock[0]):
            execute_bounded(driver, 125, "SELECT 1")
        self.assertEqual(calls[-1][1]["timeout"], 5)
        self.assertEqual(calls[-1][1]["_statement_params"]["STATEMENT_TIMEOUT_IN_SECONDS"], 5)

    def test_configuration_time_is_spent_before_workload_submission(self):
        clock = [100]
        calls = []

        def driver(sql, **kwargs):
            calls.append((sql, kwargs))
            clock[0] = 125

        with patch("airline_warehouse.deadlines.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(TimeoutError):
                execute_bounded(driver, 125, "SELECT 1")
        self.assertEqual(len(calls), 1)

    def test_nested_operation_cannot_restore_a_larger_server_deadline(self):
        from contextlib import contextmanager

        class Driver:
            def __init__(self):
                self.calls = []

            @contextmanager
            def cursor(self):
                yield self

            def execute(self, sql, **kwargs):
                self.calls.append(sql)

        driver = Driver()
        with patch("airline_warehouse.deadlines.time.monotonic", return_value=100):
            bounded = DeadlineConnection(DeadlineConnection(driver, 100), 5)
            with bounded.cursor() as cur:
                cur.execute("SELECT 1")
        self.assertEqual(len(driver.calls), 2)
        self.assertIn("STATEMENT_TIMEOUT_IN_SECONDS=5", driver.calls[0])

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

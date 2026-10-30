import importlib.util
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from airline_warehouse.connection import connect_as


@unittest.skipUnless(importlib.util.find_spec("snowflake"), "Requires the optional connector extra")
class ConnectionBoundaryTests(unittest.TestCase):
    def test_only_transient_login_retries_once_without_resetting_deadline(self):
        from snowflake.connector.errors import OperationalError

        class Driver:
            @contextmanager
            def cursor(self):
                yield self

            def execute(self, *args, **kwargs):
                pass

            def fetchone(self):
                return ("DC50202", "AWS_US_EAST_2", "AIRLINE_PUBLISHER_ROLE", "AIRLINE_PUBLISHER")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = root / ".snowflake/airline-analytics/publisher.p8"
            key.parent.mkdir(parents=True)
            key.touch(mode=0o600)
            for errors, expected_calls in (
                ([OperationalError(errno=250001), Driver()], 2),
                ([OperationalError(errno=250001), OperationalError(errno=250001)], 2),
                ([OperationalError(errno=12345)], 1),
                ([ValueError("deterministic config failure")], 1),
            ):
                with (
                    self.subTest(expected_calls=expected_calls),
                    patch("airline_warehouse.connection.Path.home", return_value=root),
                    patch("snowflake.connector.connect", side_effect=errors) as wire,
                    patch(
                        "airline_warehouse.connection.time.monotonic", side_effect=[50] + [55] * 20
                    ),
                ):
                    try:
                        connect_as("publisher", deadline=60)
                    except (OperationalError, ValueError):
                        pass
                    self.assertEqual(wire.call_count, expected_calls)
                    if expected_calls == 2:
                        self.assertEqual(wire.call_args_list[0].kwargs["login_timeout"], 10)
                        self.assertEqual(wire.call_args_list[1].kwargs["login_timeout"], 5)

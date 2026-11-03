import importlib.util
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from airline_warehouse.connection import connect_as


@unittest.skipUnless(importlib.util.find_spec("snowflake"), "Requires the optional connector extra")
class ConnectionBoundaryTests(unittest.TestCase):
    def test_cloud_dbt_credentials_refuse_identity_override_and_do_not_use_key_files(self):
        from airline_warehouse.cloud_identity import dbt_parameters

        expected = {
            "account": "LMOOEWP-DQ15927",
            "user": "AIRLINE_DEV",
            "role": "AIRLINE_DEV_ROLE",
            "database": "AIRLINE_DB",
            "warehouse": "AIRLINE_DEV_WH",
            "private_key": None,
        }
        with patch("airline_warehouse.cloud_identity.private_key", return_value=b"der"):
            result = dbt_parameters(expected, "warehouse", deadline=99999999999)
            self.assertEqual(result["private_key"], b"der")
            self.assertNotIn("private_key_file", result)
            for override in (
                {"user": "AIRLINE_PUBLISHER"},
                {"role": "ACCOUNTADMIN"},
                {"private_key_file": "/tmp/key"},
                {"password": "no"},
            ):
                with self.subTest(override=override), self.assertRaises(ValueError):
                    dbt_parameters({**expected, **override}, "warehouse", deadline=99999999999)

    def test_cloud_identity_uses_only_its_pinned_secret_without_local_fallback(self):
        from unittest.mock import Mock

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        secret = Mock()
        import json

        secret.get_secret_value.return_value = {
            "ARN": (
                "arn:aws:secretsmanager:us-east-2:336805808138:secret:"
                "airline-delay-intelligence/snowflake/publisher-m6I7eB"
            ),
            "VersionId": "be15541a-9e70-44bb-912a-220129a44002",
            "SecretString": json.dumps(
                {
                    "contract": "snowflake-keypair-v1",
                    "account": "LMOOEWP-DQ15927",
                    "user": "AIRLINE_PUBLISHER",
                    "role": "AIRLINE_PUBLISHER_ROLE",
                    "private_key_pem": pem,
                }
            ),
        }
        with (
            patch.dict("os.environ", {"AIRLINE_CLOUD_IDENTITY": "publisher"}),
            patch("boto3.client", return_value=secret),
            patch(
                "airline_warehouse.connection._login", side_effect=RuntimeError("stop before wire")
            ) as login,
        ):
            with self.assertRaisesRegex(RuntimeError, "stop before wire"):
                connect_as("publisher", deadline=99999999999)
            params = login.call_args.args[0]
            self.assertIsInstance(params["private_key"], bytes)
            self.assertNotIn("private_key_file", params)
            self.assertEqual(params["user"], "AIRLINE_PUBLISHER")
            self.assertEqual(
                secret.get_secret_value.call_args.kwargs["VersionId"],
                "be15541a-9e70-44bb-912a-220129a44002",
            )
            with self.assertRaises(ValueError):
                connect_as("builder")

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

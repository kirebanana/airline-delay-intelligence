"""Probe behavior without network, credentials or secret-value requests."""

import hashlib
import io
import unittest
from unittest.mock import Mock

from airline_warehouse.connectivity_probe import run_probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.body = b'{"selected":"fixture"}'
        self.request = {
            "request_id": "a" * 32,
            "kind": "warehouse",
            "deadline_epoch": 2000000000,
            "manifest_key": "manifests/prepared/bts/2025-01/" + "b" * 64 + "/" + "c" * 64 + ".json",
            "manifest_sha256": hashlib.sha256(self.body).hexdigest(),
        }
        self.s3 = Mock()
        self.s3.get_object.return_value = {"Body": io.BytesIO(self.body)}
        self.sts = Mock()
        self.sts.get_caller_identity.return_value = {
            "Account": "336805808138",
            "Arn": "arn:aws:sts::336805808138:assumed-role/airline-job-warehouse/task123",
        }
        from botocore.exceptions import ClientError

        self.s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
            "HeadObject",
        )
        self.factory = Mock(
            side_effect=lambda service, remaining: self.s3 if service == "s3" else self.sts
        )
        self.https = Mock(return_value=200)

    def probe(self, request=None):
        return run_probe(
            self.request if request is None else request,
            client_factory=self.factory,
            https_probe=self.https,
            now=lambda: 1999999900,
        )

    def test_success_checks_exact_principal_manifest_tls_and_state_denial(self):
        result = self.probe()
        self.assertEqual(result["status"], "CONNECTIVITY_ONLY")
        self.assertFalse(result["snowflake_authenticated"])
        self.assertEqual(result["state_access"], "DENIED")
        self.assertEqual(self.s3.put_object.call_args.kwargs["IfNoneMatch"], "*")
        self.assertEqual(self.s3.put_object.call_args.kwargs["ServerSideEncryption"], "AES256")
        self.assertLess(len(self.s3.put_object.call_args.kwargs["Body"]), 16384)
        self.https.assert_called_once_with("lmooewp-dq15927.snowflakecomputing.com", 5)

    def test_unknown_scope_or_expired_deadline_refuses_all_network_calls(self):
        for patch in (
            {"deadline_epoch": 1},
            {"kind": "reader"},
            {"manifest_key": "original/source.zip"},
            {"password": "never"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.probe({**self.request, **patch})
        self.factory.assert_not_called()
        self.https.assert_not_called()

    def test_wrong_role_corrupt_manifest_or_unexpected_state_access_never_writes_success(self):
        self.sts.get_caller_identity.return_value["Account"] = "111111111111"
        with self.assertRaises(ValueError):
            self.probe()
        self.s3.put_object.assert_not_called()
        self.sts.get_caller_identity.return_value["Account"] = "336805808138"
        self.s3.get_object.return_value = {"Body": io.BytesIO(b"corrupt")}
        with self.assertRaises(ValueError):
            self.probe()
        self.s3.put_object.assert_not_called()
        self.s3.get_object.return_value = {"Body": io.BytesIO(self.body)}
        self.s3.head_object.side_effect = None
        with self.assertRaises(ValueError):
            self.probe()
        self.s3.put_object.assert_not_called()

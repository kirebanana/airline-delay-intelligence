"""Offline boundary tests; no AWS credentials, tasks or network calls."""

import json
import unittest

from airline_warehouse.cloud_results import CloudResultUncertain, read_completed_result


class CloudResultTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "contract": "ecs-stage-result-v1",
            "request_id": "a" * 32,
            "target": "test_cloud",
            "stage": "warehouse",
            "attempt": 1,
            "deadline_epoch": 2000000000,
            "processing_contract": "b" * 64,
            "image_digest": "sha256:" + "c" * 64,
            "task_definition_arn": (
                "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-warehouse:1"
            ),
            "task_arn": "arn:aws:ecs:us-east-2:336805808138:task/airline-jobs/" + "d" * 32,
            "execution_arn": "arn:aws:states:us-east-2:336805808138:execution:airline-refresh:run1",
            "workflow_version_arn": (
                "arn:aws:states:us-east-2:336805808138:stateMachine:airline-refresh:1"
            ),
            "inputs": {"2025-01": "e" * 64},
        }
        self.result = {
            **self.expected,
            "status": "COMPLETED",
            "completed_epoch": 1999999999,
            "output": {
                "key": "reports/build/" + "a" * 32 + "/candidate.json",
                "sha256": "f" * 64,
            },
        }

    def read(self, result=None, exits=None):
        body = json.dumps(self.result if result is None else result).encode()
        return read_completed_result(
            body, self.expected, essential_exits={"job": 0} if exits is None else exits
        )

    def test_success_requires_exact_execution_task_image_inputs_and_deadline(self):
        self.assertEqual(self.read(), self.result["output"])
        for field, value in self.expected.items():
            bad = {**self.result, field: 2 if type(value) is int else {}}
            with self.subTest(field=field), self.assertRaises(CloudResultUncertain):
                self.read(bad)

    def test_successful_manifest_does_not_override_a_failed_or_unknown_exit(self):
        for exits in ({}, {"job": 1}, {"job": None}, {"job": False}, {"other": 0}):
            with self.subTest(exits=exits), self.assertRaises(CloudResultUncertain):
                self.read(exits=exits)

    def test_essential_success_does_not_override_incomplete_or_uncertain_result(self):
        for status in ("RUNNING", "FAILED", "RECOVERY_REQUIRED", None):
            with self.subTest(status=status), self.assertRaises(CloudResultUncertain):
                self.read({**self.result, "status": status})

    def test_result_payload_is_bounded_and_duplicate_fields_are_not_accepted(self):
        for body in (b"{}" * 9000, b'{"status":"FAILED","status":"COMPLETED"}', b"null", b"\xff"):
            with self.subTest(body=body[:20]), self.assertRaises(CloudResultUncertain):
                read_completed_result(body, self.expected, essential_exits={"job": 0})

    def test_late_completion_bad_output_and_unknown_fields_fail_closed(self):
        variants = [
            {**self.result, "completed_epoch": self.expected["deadline_epoch"] + 1},
            {**self.result, "completed_epoch": float("nan")},
            {**self.result, "output": {"key": "original/bts/source.zip", "sha256": "f" * 64}},
            {**self.result, "output": {"key": "reports/build/../wrong", "sha256": "f" * 64}},
            {
                **self.result,
                "output": {"key": "reports/build/other/request.json", "sha256": "f" * 64},
            },
            {**self.result, "credentials": "must never travel through workflow state"},
        ]
        for result in variants:
            with self.subTest(result=result), self.assertRaises(CloudResultUncertain):
                self.read(result)

    def test_wrong_account_unversioned_workflow_or_excess_attempt_is_not_a_binding(self):
        for field, value in (
            ("attempt", 3),
            ("workflow_version_arn", self.expected["workflow_version_arn"].rsplit(":", 1)[0]),
            ("task_arn", self.expected["task_arn"].replace("336805808138", "111111111111")),
        ):
            expected = {**self.expected, field: value}
            result = {**self.result, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                read_completed_result(
                    json.dumps(result).encode(), expected, essential_exits={"job": 0}
                )

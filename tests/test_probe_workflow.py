import unittest

from airline_warehouse.probe_workflow import definition


class ProbeWorkflowTests(unittest.TestCase):
    def test_sync_requires_exit_and_bounded_request_bound_report_without_stdout(self):
        d = definition()
        states = d["States"]
        self.assertEqual(d["TimeoutSeconds"], 600)
        self.assertEqual(states["RunProbe"]["Resource"], "arn:aws:states:::ecs:runTask.sync")
        self.assertNotIn("Retry", states["RunProbe"])
        self.assertEqual(
            states["CheckSize"]["Choices"][0]["And"][0]["NumericLessThanEquals"], 16384
        )
        checks = states["CheckReport"]["Choices"][0]["And"]
        self.assertIn(
            {"Variable": "$.result.request_id", "StringEqualsPath": "$.probe.request_id"}, checks
        )
        self.assertEqual(states["Uncertain"]["Error"], "RECOVERY_REQUIRED")
        self.assertEqual(states["ReadReport"]["Resource"], "arn:aws:states:::aws-sdk:s3:getObject")

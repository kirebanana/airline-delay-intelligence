import unittest

from airline_warehouse.cloud_workflow import definition


class CloudWorkflowTests(unittest.TestCase):
    def test_four_fixed_stages_have_sync_exit_digest_and_checked_s3_results(self):
        tasks = {
            kind: f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:1"
            for kind in ("acquisition", "warehouse", "publisher")
        }
        d = definition(tasks, "sha256:" + "a" * 64, "b" * 64)
        self.assertEqual(d["TimeoutSeconds"], 3600)
        for mode in ("admit", "acquisition", "warehouse", "publish"):
            state = d["States"][mode + "Run"]
            self.assertEqual(state["Resource"], "arn:aws:states:::ecs:runTask.sync")
            self.assertNotIn("Retry", state)
            self.assertIn("CheckControl", d["States"][mode + "DecodeControl"]["Next"])
            self.assertEqual(d["States"][mode + "CheckExit"]["Default"], "Uncertain")
        self.assertEqual(d["States"]["Uncertain"]["Error"], "RECOVERY_REQUIRED")

    def test_exact_replay_finishes_without_another_data_task_and_only_reads_retry(self):
        tasks = {
            kind: f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:1"
            for kind in ("acquisition", "warehouse", "publisher")
        }
        states = definition(tasks, "sha256:" + "a" * 64, "b" * 64)["States"]
        self.assertTrue(states["ReplayComplete"]["End"])
        self.assertEqual(states["admitOutcome"]["Choices"][0]["Next"], "ReplayComplete")
        self.assertEqual(
            states["warehouseCompose"]["Parameters"]["contract"], "cloud-stage-request-v2"
        )
        for state in states.values():
            if "Retry" in state:
                self.assertIn(state["Resource"].rsplit(":", 1)[-1], ("headObject", "getObject"))
                self.assertEqual(state["Retry"][0]["MaxAttempts"], 1)
                self.assertNotIn("States.ALL", state["Retry"][0]["ErrorEquals"])

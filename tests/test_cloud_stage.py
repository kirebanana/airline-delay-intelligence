import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from airline_warehouse.cloud_stage import run_stage, task_identity, validate_request


class CloudStageTests(unittest.TestCase):
    def request(self):
        return {
            "contract": "cloud-stage-request-v1",
            "mode": "warehouse",
            "request_id": "a" * 32,
            "target": "test_" + "b" * 16,
            "deadline_epoch": int(time.time()) + 120,
            "artifacts": [
                {
                    "key": "manifests/prepared/bts/2025-01/" + "c" * 64 + "/" + "d" * 64 + ".json",
                    "sha256": "e" * 64,
                }
            ],
            "dependency": None,
            "authority": {
                "target": "test_" + "b" * 16,
                "request_id": "a" * 32,
                "attempt": "c" * 32,
                "fence": 1,
                "status": "RUNNING",
            },
            "budget": {
                "baseline_credits": "1.97",
                "max_elapsed_seconds": None,
                "additional_credit_limit": None,
                "recovery_reserve_credits": "0.5",
                "elapsed_seconds": 4030.0,
                "operations": [],
            },
            "deployment": {
                "execution_arn": (
                    "arn:aws:states:us-east-2:336805808138:execution:airline-refresh:run1"
                ),
                "workflow_version_arn": (
                    "arn:aws:states:us-east-2:336805808138:stateMachine:airline-refresh:1"
                ),
                "task_definition_arn": (
                    "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-warehouse:1"
                ),
                "image_digest": "sha256:" + "e" * 64,
                "processing_contract": "f" * 64,
                "attempt": 1,
            },
        }

    def test_stage_requires_matching_role_explicit_inputs_and_finite_original_budget(self):
        r = self.request()
        self.assertEqual(validate_request(r, "warehouse"), r)
        for update in (
            {"mode": "publisher"},
            {"target": "january"},
            {"deadline_epoch": 1},
            {"password": "no"},
            {"artifacts": []},
            {"budget": {}},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_request({**r, **update}, "warehouse")

    def test_duplicate_or_unknown_stage_intent_refuses_all_sql(self):
        r = self.request()
        store = Mock()
        store.write.side_effect = RuntimeError("create-only intent already exists or ack lost")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"AIRLINE_CLOUD_IDENTITY": "warehouse"}),
            patch("airline_warehouse.cloud_stage.task_identity", return_value="task"),
            patch("airline_warehouse.warehouse.processing_contract", return_value="f" * 64),
            patch("airline_warehouse.cloud_stage.sdk_factory"),
            patch("airline_warehouse.cloud_stage.ReportStore", return_value=store),
            patch("airline_warehouse.cloud_stage.connect_as") as login,
        ):
            with self.assertRaises(RuntimeError):
                run_stage(r, Path(tmp))
            login.assert_not_called()

    def test_v2_selection_reference_keeps_large_month_map_out_of_task_request(self):
        r = self.request()
        r.update(
            contract="cloud-stage-request-v2",
            artifacts={"key": "manifests/selections/" + "a" * 64 + ".json", "sha256": "a" * 64},
        )
        self.assertEqual(validate_request(r, "warehouse"), r)
        r["artifacts"]["key"] = "prepared/secret"
        with self.assertRaises(ValueError):
            validate_request(r, "warehouse")

    def test_task_metadata_must_match_actual_cluster_and_definition(self):
        import io
        import json

        metadata = {
            "TaskARN": "arn:aws:ecs:us-east-2:336805808138:task/airline-jobs/" + "a" * 32,
            "Cluster": "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs",
            "Family": "airline-stage-warehouse",
            "Revision": "1",
        }
        uri = "http://169.254.170.2/v4/fixture"
        with patch.dict("os.environ", {"ECS_CONTAINER_METADATA_URI_V4": uri}):
            with patch(
                "urllib.request.urlopen", return_value=io.BytesIO(json.dumps(metadata).encode())
            ):
                self.assertEqual(task_identity(self.request()["deployment"]), metadata["TaskARN"])
            metadata["Revision"] = "2"
            with patch(
                "urllib.request.urlopen", return_value=io.BytesIO(json.dumps(metadata).encode())
            ):
                with self.assertRaises(ValueError):
                    task_identity(self.request()["deployment"])

import json
import unittest
from pathlib import Path

from airline_warehouse.cloud_workflow import definition


class JobDeploymentTests(unittest.TestCase):
    def test_registered_graph_template_matches_the_tested_generator(self):
        root = Path(__file__).resolve().parents[1]
        tasks = {
            k: f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{k}:1"
            for k in ("acquisition", "warehouse", "publisher")
        }
        image, contract = "sha256:" + "a" * 64, "b" * 64
        text = (root / "infra/jobs/refresh.asl.json.tftpl").read_text()
        for key, value in {
            **{"task_" + k: v for k, v in tasks.items()},
            "image_digest": image,
            "processing_contract": contract,
        }.items():
            text = text.replace("${" + key + "}", value)
        self.assertEqual(json.loads(text), definition(tasks, image, contract))

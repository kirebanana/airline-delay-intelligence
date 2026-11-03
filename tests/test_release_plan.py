import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import airline_warehouse.release_plan as release_plan
from airline_warehouse.cloud_workflow import definition
from airline_warehouse.release_plan import (
    KINDS,
    REPOSITORY,
    ROLE,
    inspect_release_plan,
    validate_saved_graph_source,
)


class ReleasePlanTests(unittest.TestCase):
    def test_saved_source_rejects_graph_bypass_and_archive_source_mismatch(self):
        source = b"""definition = templatefile("${path.module}/refresh.asl.json.tftpl", {
            task_acquisition = aws_ecs_task_definition.stage["acquisition"].arn
            task_warehouse = aws_ecs_task_definition.stage["warehouse"].arn
            task_publisher = aws_ecs_task_definition.stage["publisher"].arn
            image_digest = var.image_digest
            processing_contract = var.processing_contract
        })
        lifecycle { prevent_destroy = true }"""
        with patch.object(
            release_plan, "QUALIFIED_MAIN_SHA256", hashlib.sha256(source).hexdigest()
        ):
            validate_saved_graph_source(source, source)
            with self.assertRaisesRegex(ValueError, "configuration"):
                validate_saved_graph_source(source, source + b"# changed")
            bypass = source.replace(b"templatefile(", b"evil(")
            with self.assertRaisesRegex(ValueError, "graph"):
                validate_saved_graph_source(bypass, bypass)
            commented_decoy = b"/* " + source + b" */\ndefinition = evil()"
            with self.assertRaisesRegex(ValueError, "graph"):
                validate_saved_graph_source(commented_decoy, commented_decoy)

    def plan(self):
        changes = []
        for kind in KINDS:
            task = {
                "arn": f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:1",
                "family": "airline-stage-" + kind,
                "cpu": "256",
                "memory": "1024",
                "task_role_arn": ROLE + "airline-job-" + kind,
                "execution_role_arn": ROLE + "airline-job-execution",
                "network_mode": "awsvpc",
                "requires_compatibilities": ["FARGATE"],
                "runtime_platform": [],
                "tags_all": {},
                "skip_destroy": True,
                "track_latest": False,
                "volume": [{"name": "scratch"}],
                "container_definitions": json.dumps(
                    [
                        {
                            "name": "job",
                            "image": REPOSITORY + "@sha256:" + "a" * 64,
                            "user": "65532:65532",
                            "readonlyRootFilesystem": True,
                        }
                    ]
                ),
            }
            after = copy.deepcopy(task)
            after["arn"] = after["arn"][:-1] + "2"
            after["container_definitions"] = after["container_definitions"].replace(
                "a" * 64, "b" * 64
            )
            changes.append(
                {
                    "address": f'aws_ecs_task_definition.stage["{kind}"]',
                    "mode": "managed",
                    "type": "aws_ecs_task_definition",
                    "index": kind,
                    "change": {"actions": ["create", "delete"], "before": task, "after": after},
                }
            )
        workflow = {
            "name": "airline-isolated-refresh",
            "type": "STANDARD",
            "role_arn": ROLE + "airline-refresh-workflow",
            "publish": True,
        }
        changes.append(
            {
                "address": "aws_sfn_state_machine.refresh",
                "mode": "managed",
                "type": "aws_sfn_state_machine",
                "change": {
                    "actions": ["update"],
                    "before": workflow,
                    "after": {
                        **workflow,
                        "definition": json.dumps(
                            definition(
                                {
                                    k: "arn:aws:ecs:us-east-2:336805808138:task-definition/"
                                    + f"airline-stage-{k}:2"
                                    for k in KINDS
                                },
                                "sha256:" + "b" * 64,
                                "c" * 64,
                            )
                        ),
                    },
                },
            }
        )
        return {
            "resource_changes": changes,
            "variables": {"processing_contract": {"value": "c" * 64}},
        }

    def test_arbitrary_saved_workflow_cannot_bypass_template(self):
        plan = self.plan()
        plan["resource_changes"][-1]["change"]["after"]["definition"] = json.dumps(
            {"StartAt": "Bypass", "States": {"Bypass": {"Type": "Succeed"}}}
        )
        with self.assertRaisesRegex(ValueError, "graph"):
            inspect_release_plan(plan, "sha256:" + "b" * 64)

    def test_exact_retained_revision_promotion_is_review_not_authorization(self):
        result = inspect_release_plan(self.plan(), "sha256:" + "b" * 64)
        self.assertEqual(result["task_revisions"], 3)
        self.assertFalse(result["apply_authorized"])
        self.assertFalse(result["data_launch"])

    def partial_plan(self):
        plan = self.plan()
        retained = copy.deepcopy(plan["resource_changes"][0])
        retained["deposed"] = "66e94578"
        retained["change"]["actions"] = ["delete"]
        retained["change"]["after"] = None
        retained["change"]["before"]["arn"] = (
            "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-acquisition:4"
        )
        plan["resource_changes"].append(retained)
        return plan

    def test_partial_apply_requires_explicit_retained_deposed_review(self):
        plan = self.partial_plan()
        with self.assertRaises(ValueError):
            inspect_release_plan(plan, "sha256:" + "b" * 64)
        result = inspect_release_plan(plan, "sha256:" + "b" * 64, allow_retained_deposed=True)
        self.assertEqual(result["retained_deposed_state_retirements"], 1)

    def test_partial_apply_never_allows_remote_delete_or_foreign_family(self):
        for mutation in ("retention", "arn", "type", "action", "deposed"):
            plan = self.partial_plan()
            retained = plan["resource_changes"][-1]
            if mutation == "retention":
                retained["change"]["before"]["skip_destroy"] = False
            elif mutation == "arn":
                retained["change"]["before"]["arn"] = (
                    "arn:aws:ecs:us-east-2:336805808138:task-definition/unrelated:4"
                )
            elif mutation == "type":
                retained["type"] = "aws_iam_role"
            elif mutation == "action":
                retained["change"]["actions"] = ["delete", "create"]
            else:
                retained["deposed"] = "unverified"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                inspect_release_plan(plan, "sha256:" + "b" * 64, allow_retained_deposed=True)

    def test_unexpected_roles_secrets_commands_platform_or_deletions_refuse(self):
        for mutation in ("role", "secret", "command", "retention", "resource", "volume", "delete"):
            plan = self.plan()
            first = plan["resource_changes"][0]["change"]
            if mutation == "role":
                first["after"]["task_role_arn"] = ROLE + "admin"
            elif mutation in ("secret", "command"):
                container = json.loads(first["after"]["container_definitions"])
                container[0]["secrets" if mutation == "secret" else "command"] = ["unexpected"]
                first["after"]["container_definitions"] = json.dumps(container)
            elif mutation == "retention":
                first["after"]["skip_destroy"] = False
            elif mutation == "resource":
                plan["resource_changes"].append({"address": "aws_iam_role.extra"})
            elif mutation == "volume":
                first["after"]["volume"][0]["host_path"] = "/unexpected"
            else:
                first["actions"] = ["delete", "create"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                inspect_release_plan(plan, "sha256:" + "b" * 64)

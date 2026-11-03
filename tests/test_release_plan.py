import copy
import json
import unittest

from airline_warehouse.release_plan import KINDS, REPOSITORY, ROLE, inspect_release_plan


class ReleasePlanTests(unittest.TestCase):
    def plan(self):
        changes = []
        for kind in KINDS:
            task = {
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
                    "after": {**workflow, "definition": None},
                },
            }
        )
        return {"resource_changes": changes}

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

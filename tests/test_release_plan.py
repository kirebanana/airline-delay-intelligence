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

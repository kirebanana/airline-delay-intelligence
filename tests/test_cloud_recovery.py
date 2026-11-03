import copy
import json
import unittest

from airline_warehouse.cloud_recovery import terminal_cloud_scope


class CloudRecoveryTests(unittest.TestCase):
    def fixture(self):
        rid, target = "a" * 32, "test_" + "b" * 16
        arn = "arn:aws:states:us-east-2:336805808138:execution:airline-isolated-refresh:case"
        execution = {
            "status": "ABORTED",
            "executionArn": arn,
            "input": json.dumps({"run": {"request_id": rid, "target": target}}),
        }
        stage = {
            "request_id": rid,
            "target": target,
            "deployment": {"execution_arn": arn, "task_definition_arn": "definition"},
        }
        task = {
            "taskArn": "task",
            "lastStatus": "STOPPED",
            "taskDefinitionArn": "definition",
            "clusterArn": "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs",
            "overrides": {
                "containerOverrides": [
                    {
                        "name": "job",
                        "environment": [
                            {"name": "AIRLINE_STAGE_REQUEST", "value": json.dumps(stage)}
                        ],
                    }
                ]
            },
        }
        events = [
            {"event": "session", "session_id": 42, "identity": "builder"},
            {"event": "query_intent", "session_id": 42},
        ]
        return execution, ["task"], [task], events

    def test_stopped_cloud_tasks_identify_sessions_but_never_claim_sql_terminal(self):
        scope = terminal_cloud_scope(*self.fixture())
        self.assertEqual(scope["sessions"], {42: "builder"})
        self.assertNotIn("cleanup", scope)

    def test_running_unknown_or_other_scope_work_refuses_recovery(self):
        for kind in (
            "running_execution",
            "unknown_launch",
            "running_task",
            "wrong_request",
            "missing_session",
        ):
            args = copy.deepcopy(self.fixture())
            if kind == "running_execution":
                args[0]["status"] = "RUNNING"
            elif kind == "unknown_launch":
                args[1].append("unknown")
            elif kind == "running_task":
                args[2][0]["lastStatus"] = "RUNNING"
            elif kind == "wrong_request":
                args[2][0]["overrides"]["containerOverrides"][0]["environment"][0]["value"] = "{}"
            else:
                args[3].pop(0)
            with self.subTest(kind=kind), self.assertRaises((ValueError, KeyError)):
                terminal_cloud_scope(*args)

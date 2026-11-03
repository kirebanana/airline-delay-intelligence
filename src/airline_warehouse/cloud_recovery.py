"""Attended cloud evidence admission before originating-identity SQL recovery.

Callers supply freshly collected full execution/task/journal evidence. This module
never launches, stops or assumes SQL termination from an ECS status. Unknown
launches and incomplete evidence refuse recovery rather than inferring absence.
"""

import json
import re


def terminal_cloud_scope(execution, scheduled_tasks, tasks, events):
    """Verify known terminal producers and return exact originating SQL sessions."""
    if execution.get("status") not in {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}:
        raise ValueError("Execution must be terminal before attended SQL recovery")
    request = json.loads(execution["input"])["run"]
    rid, target = request["request_id"], request["target"]
    if not re.fullmatch(r"[a-f0-9]{32}", rid) or not re.fullmatch(r"test_[a-f0-9]{16}", target):
        raise ValueError("Recovery only admits explicit isolated project targets")
    if not scheduled_tasks or len(scheduled_tasks) != len(tasks):
        raise ValueError("Unknown or unaccounted cloud launch; reconcile before recovery")
    by_arn = {task["taskArn"]: task for task in tasks}
    if len(by_arn) != len(tasks) or set(scheduled_tasks) != set(by_arn):
        raise ValueError("Known launches do not match exact task evidence")
    for task in tasks:
        if (
            task.get("lastStatus") != "STOPPED"
            or task.get("clusterArn") != "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs"
        ):
            raise ValueError("A producer is still running or belongs to another cluster")
        overrides = task["overrides"]["containerOverrides"]
        if len(overrides) != 1 or overrides[0]["name"] != "job":
            raise ValueError("Unexpected task producer")
        values = [
            x["value"]
            for x in overrides[0].get("environment", [])
            if x["name"] == "AIRLINE_STAGE_REQUEST"
        ]
        if len(values) != 1:
            raise ValueError("Missing originating task request")
        stage = json.loads(values[0])
        if (
            stage["request_id"] != rid
            or stage["target"] != target
            or stage["deployment"]["execution_arn"] != execution["executionArn"]
            or stage["deployment"]["task_definition_arn"] != task["taskDefinitionArn"]
        ):
            raise ValueError("Task belongs to a different execution/request/deployment")
    sessions = {}
    for event in events:
        if event["event"] == "stage_intent" and (
            event["request_id"] != rid or event["target"] != target
        ):
            raise ValueError("Journal contains another request")
        if event["event"] == "session":
            sid, identity = event["session_id"], event["identity"]
            if (
                identity not in {"builder", "publisher"}
                or sessions.setdefault(sid, identity) != identity
            ):
                raise ValueError("Conflicting originating session identity")
    if any(e.get("session_id") not in sessions for e in events if e["event"] == "query_intent"):
        raise ValueError("Query has no known originating session")
    return {"request_id": rid, "target": target, "attempt": rid, "sessions": sessions}

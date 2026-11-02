"""Completed small S3 result + actual essential exit -> verified stage output.

No SDK, launch/retry, SQL or publication side effects. A caller must obtain the
task identity/exits from ECS and the pinned deployment/request binding separately;
a task's self-reported manifest is never execution success by itself.
"""

import json
import re

MAX_RESULT_BYTES = 16 * 1024
_STAGES = {"acquisition": "acquisition", "warehouse": "build", "publisher": "publication"}
_FIELDS = {
    "contract",
    "request_id",
    "target",
    "stage",
    "attempt",
    "deadline_epoch",
    "processing_contract",
    "image_digest",
    "task_definition_arn",
    "task_arn",
    "execution_arn",
    "workflow_version_arn",
    "inputs",
}
_ECS = "arn:aws:ecs:us-east-2:336805808138:"
_STATES = "arn:aws:states:us-east-2:336805808138:"


class CloudResultUncertain(RuntimeError):
    """No automatic retry/admission: inspect the exact execution/task/result."""


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _binding(expected):
    if not isinstance(expected, dict) or set(expected) != _FIELDS:
        raise ValueError("Exact pinned stage binding required")
    if (
        expected["contract"] != "ecs-stage-result-v1"
        or not _matches(r"[a-f0-9]{32}", expected["request_id"])
        or not _matches(r"january|test_[a-z0-9_]{1,48}", expected["target"])
        or not isinstance(expected["stage"], str)
        or expected["stage"] not in _STAGES
        or type(expected["attempt"]) is not int
        or expected["attempt"] not in (1, 2)
        or type(expected["deadline_epoch"]) is not int
        or expected["deadline_epoch"] <= 0
        or not _matches(r"[a-f0-9]{64}", expected["processing_contract"])
        or not _matches(r"sha256:[a-f0-9]{64}", expected["image_digest"])
        or not _matches(
            _ECS + r"task-definition/[A-Za-z0-9_-]+:[1-9][0-9]*", expected["task_definition_arn"]
        )
        or not _matches(_ECS + r"task/[A-Za-z0-9_-]+/[a-f0-9]{32}", expected["task_arn"])
        or not _matches(
            _STATES + r"execution:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+", expected["execution_arn"]
        )
        or not _matches(
            _STATES + r"stateMachine:[A-Za-z0-9_-]+:[1-9][0-9]*", expected["workflow_version_arn"]
        )
    ):
        raise ValueError("Invalid stage identity, immutable revision or absolute deadline")
    inputs = expected["inputs"]
    if (
        not isinstance(inputs, dict)
        or not 1 <= len(inputs) <= 36
        or any(
            not _matches(r"202[3-5]-(0[1-9]|1[0-2])", month)
            or not _matches(r"[a-f0-9]{64}", artifact)
            for month, artifact in inputs.items()
        )
    ):
        raise ValueError("Exact selected baseline artifact identities required")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate control field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite control number")


def read_completed_result(body, expected, *, essential_exits):
    """Return only a checked report reference; uncertain results never imply retry.

    This validator does not hash/fetch the referenced report, prove SQL terminal,
    retire publication authority, or extend the shared across-attempt deadline.
    Those remain responsibilities of their existing explicit execution boundaries.
    """
    _binding(expected)
    if (
        not isinstance(essential_exits, dict)
        or set(essential_exits) != {"job"}
        or type(essential_exits["job"]) is not int
        or essential_exits["job"] != 0
        or not isinstance(body, bytes)
        or not 0 < len(body) <= MAX_RESULT_BYTES
    ):
        raise CloudResultUncertain("Missing essential success or bounded result")
    try:
        value = json.loads(body, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if not isinstance(value, dict) or set(value) != _FIELDS | {
            "status",
            "completed_epoch",
            "output",
        }:
            raise ValueError("Unexpected control fields")
        for key in _FIELDS:
            if type(value[key]) is not type(expected[key]) or value[key] != expected[key]:
                raise ValueError("Result binding mismatch")
        if (
            value["status"] != "COMPLETED"
            or type(value["completed_epoch"]) is not int
            or not 0 < value["completed_epoch"] <= expected["deadline_epoch"]
        ):
            raise ValueError("Incomplete or late stage")
        output = value["output"]
        prefix = f"reports/{_STAGES[expected['stage']]}/{expected['request_id']}/"
        if (
            not isinstance(output, dict)
            or set(output) != {"key", "sha256"}
            or not isinstance(output["key"], str)
            or not output["key"].startswith(prefix)
            or not _matches(r"[A-Za-z0-9_-]+[.]json", output["key"][len(prefix) :])
            or not _matches(r"[a-f0-9]{64}", output["sha256"])
        ):
            raise ValueError("Invalid request-scoped report reference")
        return dict(output)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise CloudResultUncertain(
            "Unverified stage result; reconcile before another attempt"
        ) from error

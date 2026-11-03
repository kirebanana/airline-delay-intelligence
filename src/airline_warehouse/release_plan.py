"""Fail-closed review of immutable application-release plans, never authorization."""

import json
import re

from airline_warehouse.cloud_workflow import definition

KINDS = ("acquisition", "warehouse", "publisher")
ROLE = "arn:aws:iam::336805808138:role/"
REPOSITORY = "336805808138.dkr.ecr.us-east-2.amazonaws.com/airline-delay-intelligence"


def validate_saved_graph_source(saved_main, current_main):
    """Bind unknown planned graphs to the exact archived, checked expression."""
    if saved_main != current_main:
        raise ValueError("Saved plan was not produced by this reviewed release configuration")
    expression = re.search(r"\bdefinition\s*=\s*(.*?)\n\s*lifecycle", saved_main.decode(), re.S)
    expected = """templatefile("${path.module}/refresh.asl.json.tftpl", {
        task_acquisition = aws_ecs_task_definition.stage["acquisition"].arn
        task_warehouse = aws_ecs_task_definition.stage["warehouse"].arn
        task_publisher = aws_ecs_task_definition.stage["publisher"].arn
        image_digest = var.image_digest
        processing_contract = var.processing_contract
    })"""
    if expression is None or re.sub(r"\s+", "", expression[1]) != re.sub(r"\s+", "", expected):
        raise ValueError("Saved graph expression must use only the exact checked template bindings")


def inspect_release_plan(plan, image_digest, *, allow_retained_deposed=False):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_digest):
        raise ValueError("A tested immutable image digest is required")
    expected = {f'aws_ecs_task_definition.stage["{k}"]' for k in KINDS} | {
        "aws_sfn_state_machine.refresh"
    }
    changes = plan.get("resource_changes", [])
    deposed = [r for r in changes if r.get("deposed")]
    if deposed:
        if not allow_retained_deposed or len(deposed) > 3:
            raise ValueError("Partial apply requires explicit retained-deposed recovery review")
        seen = set()
        for resource in deposed:
            kind = resource.get("index")
            change = resource["change"]
            before = change.get("before") or {}
            arn = (
                "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-"
                + str(kind)
                + r":[1-9][0-9]*"
            )
            if (
                kind not in KINDS
                or kind in seen
                or resource.get("address") != f'aws_ecs_task_definition.stage["{kind}"]'
                or resource.get("mode") != "managed"
                or resource.get("type") != "aws_ecs_task_definition"
                or not re.fullmatch(r"[a-f0-9]{8}", resource["deposed"])
                or change["actions"] != ["delete"]
                or change.get("after") is not None
                or before.get("skip_destroy") is not True
                or before.get("family") != "airline-stage-" + kind
                or not re.fullmatch(arn, before.get("arn", ""))
            ):
                raise ValueError("Only exact retained deposed task state may be retired")
            seen.add(kind)
        # skip_destroy is the pinned provider's no-deregister path. This retires
        # deposed Terraform bindings, not the retained AWS task definitions.
        changes = [r for r in changes if not r.get("deposed")]
    if len(changes) != 4 or {r.get("address") for r in changes} != expected:
        raise ValueError("Release plan must contain exactly three task families and one workflow")
    revisions = 0
    for resource in changes:
        if resource.get("mode") != "managed":
            raise ValueError("Unexpected data read or non-managed release change")
        change = resource["change"]
        before, after = change.get("before"), change["after"]
        if before is None or change.get("importing"):
            raise ValueError("Bootstrap/import is not an ordinary image promotion")
        if resource["type"] == "aws_ecs_task_definition":
            kind = resource["index"]
            if change["actions"] not in (["no-op"], ["create", "delete"]):
                raise ValueError("Only retained create-before-destroy task revisions are allowed")
            revisions += change["actions"] != ["no-op"]
            if not before["skip_destroy"] or not after["skip_destroy"]:
                raise ValueError("Old task revisions must remain usable")
            for key in (
                "family",
                "cpu",
                "memory",
                "task_role_arn",
                "execution_role_arn",
                "network_mode",
                "requires_compatibilities",
                "runtime_platform",
                "tags_all",
                "skip_destroy",
                "track_latest",
            ):
                if before[key] != after[key]:
                    raise ValueError(f"Platform/task contract changed: {key}")
            if (
                after["task_role_arn"] != ROLE + "airline-job-" + kind
                or after["execution_role_arn"] != ROLE + "airline-job-execution"
            ):
                raise ValueError("Unexpected task/execution role")
            old, new = (
                json.loads(before["container_definitions"]),
                json.loads(after["container_definitions"]),
            )
            if len(old) != 1 or len(new) != 1 or new[0]["image"] != REPOSITORY + "@" + image_digest:
                raise ValueError("Unexpected container or untested image")
            old[0]["image"] = new[0]["image"]
            if old != new:
                raise ValueError(
                    "Image promotion cannot change command, secrets, mounts, env or logging"
                )
            if (
                new[0].get("user") != "65532:65532"
                or not new[0].get("readonlyRootFilesystem")
                or new[0].get("secrets")
                or new[0].get("portMappings")
            ):
                raise ValueError("Unsafe workload container")
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            if not changed <= {
                "tags",
                "pid_mode",
                "ipc_mode",
                "arn",
                "arn_without_revision",
                "id",
                "revision",
                "enable_fault_injection",
                "container_definitions",
                "volume",
            }:
                raise ValueError("Unexpected task-definition change")
            for key in ("tags", "pid_mode", "ipc_mode"):
                if before.get(key) or after.get(key):
                    raise ValueError("Unexpected extra task mode/tag mutation")
            if [x["name"] for x in before["volume"]] != [x["name"] for x in after["volume"]] or [
                x["name"] for x in after["volume"]
            ] != ["scratch"]:
                raise ValueError("Unexpected task volume")
            volumes = [
                [
                    {k: v for k, v in volume.items() if k != "configure_at_launch"}
                    for volume in task["volume"]
                ]
                for task in (before, after)
            ]
            if volumes[0] != volumes[1]:
                raise ValueError("Image promotion cannot change volume backing")
        else:
            if change["actions"] not in (["no-op"], ["update"]):
                raise ValueError("Workflow replacement/deletion is forbidden")
            if (
                after["name"] != "airline-isolated-refresh"
                or after["type"] != "STANDARD"
                or after["role_arn"] != ROLE + "airline-refresh-workflow"
                or not after["publish"]
            ):
                raise ValueError("Unexpected workflow identity or version policy")
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            if not changed <= {"definition", "revision_id", "state_machine_version_arn"}:
                raise ValueError(
                    "Workflow promotion cannot change platform, logging or role contracts"
                )
    workflow = next(r for r in changes if r["type"] == "aws_sfn_state_machine")
    planned = workflow["change"]["after"].get("definition")
    contract = plan.get("variables", {}).get("processing_contract", {}).get("value", "")
    if not re.fullmatch(r"[a-f0-9]{64}", contract):
        raise ValueError("Saved graph must bind an exact processing contract")
    if planned is not None:
        tasks = {
            r["index"]: r["change"]["after"].get("arn")
            for r in changes
            if r["type"] == "aws_ecs_task_definition"
        }
        if any(not isinstance(v, str) for v in tasks.values()):
            raise ValueError("Known saved graph must bind known exact task revisions")
        if json.loads(planned) != definition(tasks, image_digest, contract):
            raise ValueError("Saved workflow graph differs from qualified generator")
    else:
        config = plan.get("configuration", {}).get("root_module", {}).get("resources", [])
        configs = [r for r in config if r.get("address") == "aws_sfn_state_machine.refresh"]
        expected_refs = {
            "path.module",
            "var.image_digest",
            "var.processing_contract",
            "aws_ecs_task_definition.stage",
        }
        for kind in KINDS:
            expected_refs |= {
                f'aws_ecs_task_definition.stage["{kind}"]',
                f'aws_ecs_task_definition.stage["{kind}"].arn',
            }
        expression = (
            configs[0].get("expressions", {}).get("definition", {}) if len(configs) == 1 else {}
        )
        if (
            len(configs) != 1
            or set(expression) != {"references"}
            or set(expression.get("references", [])) != expected_refs
            or not workflow["change"].get("after_unknown", {}).get("definition")
        ):
            raise ValueError("Unknown saved graph has unexpected template/task/variable bindings")
    return {
        "task_revisions": revisions,
        "retained_deposed_state_retirements": len(deposed),
        "retained_old_revisions": True,
        "platform_changes": False,
        "data_launch": False,
        "apply_authorized": False,
    }

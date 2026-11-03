"""Finite isolated cloud tracer stages using the existing warehouse/release logic.

Only explicit test targets are admitted by this first adapter. No implicit final
baseline, target initialization, takeover, claim retirement on uncertain work,
source download or production release mutation.
"""

import base64
import hashlib
import json
import logging
import math
import os
import re
import signal
import tempfile
import time
import urllib.request
from pathlib import Path

from airline_warehouse.cloud_artifacts import ReportStore
from airline_warehouse.cloud_selection import (
    SELECTION_KEY,
    read_selection,
    restore_weather,
    selection_digest,
    validate_reference,
)
from airline_warehouse.connection import connect_as
from airline_warehouse.connectivity_probe import BUCKET, sdk_factory
from airline_warehouse.execution import tracked
from airline_warehouse.load import execute_load, object_keys, validate_manifest

_MODES = {
    "admit": "publisher",
    "acquisition": "acquisition",
    "warehouse": "warehouse",
    "publish": "publisher",
}
_FIELDS = {
    "contract",
    "mode",
    "request_id",
    "target",
    "deadline_epoch",
    "artifacts",
    "dependency",
    "authority",
    "budget",
    "deployment",
}


def validate_request(request, identity):
    if not isinstance(request, dict) or set(request) != _FIELDS:
        raise ValueError("Exact bounded cloud-stage request required")
    mode = request["mode"]
    if not isinstance(mode, str) or _MODES.get(mode) != identity:
        raise ValueError("Wrong workload identity for this stage")
    # The operator supplies original absolute workflow/stage ceilings. Each
    # single admitted attempt is additionally clamped below to its stage budget.
    maximum = 3600
    if (
        request["contract"] not in ("cloud-stage-request-v1", "cloud-stage-request-v2")
        or not isinstance(request["request_id"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", request["request_id"])
        or not isinstance(request["target"], str)
        or not re.fullmatch(r"test_[a-f0-9]{16}", request["target"])
        or type(request["deadline_epoch"]) is not int
        or not 0 < request["deadline_epoch"] - time.time() <= maximum
    ):
        raise ValueError("Unapproved target or expired/extended stage budget")
    refs = request["artifacts"]
    if request["contract"] == "cloud-stage-request-v2":
        validate_reference(refs, SELECTION_KEY)
        refs = []
    elif not isinstance(refs, list) or len(refs) != 1:
        raise ValueError("First isolated cloud tracer requires exactly one selected month")
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or set(ref) != {"key", "sha256"}
            or not isinstance(ref["key"], str)
            or not re.fullmatch(
                r"manifests/prepared/bts/202[3-5]-(0[1-9]|1[0-2])/[a-f0-9]{64}/[a-f0-9]{64}[.]json",
                ref["key"],
            )
            or not isinstance(ref["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"])
        ):
            raise ValueError("Artifact reference escapes accepted project inputs")
    state = request["budget"]
    if (
        not isinstance(state, dict)
        or not {
            "baseline_credits",
            "max_elapsed_seconds",
            "additional_credit_limit",
            "recovery_reserve_credits",
            "elapsed_seconds",
            "operations",
        }
        <= set(state)
        or state.get("recovery_required")
        or state.get("operation_active")
    ):
        raise ValueError("Original unblocked cumulative budget required")
    elapsed = state["elapsed_seconds"]
    if (
        type(elapsed) not in (int, float)
        or not math.isfinite(elapsed)
        or elapsed < 0
        or str(state["recovery_reserve_credits"]) != "0.5"
    ):
        raise ValueError("Cannot reset cumulative accounting or recovery reserve")
    if mode in ("warehouse", "publish"):
        token = request["authority"]
        if (
            not isinstance(token, dict)
            or token.get("target") != request["target"]
            or token.get("request_id") != request["request_id"]
            or token.get("status") != "RUNNING"
        ):
            raise ValueError("Matching admission authority required")
    if mode == "publish" and request["dependency"] is None:
        raise ValueError("Publication requires exact sealed candidate reference")
    deployment = request["deployment"]
    if not isinstance(deployment, dict) or set(deployment) != {
        "execution_arn",
        "workflow_version_arn",
        "task_definition_arn",
        "image_digest",
        "processing_contract",
        "attempt",
    }:
        raise ValueError("Pinned task/image/workflow binding required")
    for field, pattern in {
        "execution_arn": (
            r"arn:aws:states:us-east-2:336805808138:execution:"
            r"airline-[A-Za-z0-9_-]+:[A-Za-z0-9_-]+"
        ),
        "workflow_version_arn": (
            r"arn:aws:states:us-east-2:336805808138:stateMachine:"
            r"airline-[A-Za-z0-9_-]+:[1-9][0-9]*"
        ),
        "task_definition_arn": (
            r"arn:aws:ecs:us-east-2:336805808138:task-definition/"
            rf"airline-stage-{identity}:[1-9][0-9]*"
        ),
        "image_digest": r"sha256:[a-f0-9]{64}",
        "processing_contract": r"[a-f0-9]{64}",
    }.items():
        if not isinstance(deployment[field], str) or not re.fullmatch(pattern, deployment[field]):
            raise ValueError("Invalid immutable deployment identity")
    if type(deployment["attempt"]) is not int or deployment["attempt"] != 1:
        raise ValueError("First tracer has no automatic retry or redrive")
    return request


def task_identity(deployment):
    uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4", "")
    if not re.fullmatch(r"http://169[.]254[.]170[.]2/v4/[A-Za-z0-9_-]+", uri):
        raise ValueError("Trusted ECS task metadata endpoint required")
    with urllib.request.urlopen(uri + "/task", timeout=5) as response:
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("Oversized task metadata")
    metadata = json.loads(body)
    definition = (
        "arn:aws:ecs:us-east-2:336805808138:task-definition/"
        + metadata["Family"]
        + ":"
        + str(metadata["Revision"])
    )
    task = metadata["TaskARN"]
    if (
        metadata["Cluster"] != "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs"
        or definition != deployment["task_definition_arn"]
        or not re.fullmatch(
            r"arn:aws:ecs:us-east-2:336805808138:task/airline-jobs/[a-f0-9]{32}", task
        )
    ):
        raise ValueError("Task metadata does not match the pinned deployment")
    return task


def _manifests(s3, references):
    values = []
    for ref in references:
        stream = s3.get_object(Bucket=BUCKET, Key=ref["key"])["Body"]
        try:
            body = stream.read(16385)
        finally:
            stream.close()
        if len(body) > 16384 or hashlib.sha256(body).hexdigest() != ref["sha256"]:
            raise ValueError("Selected manifest hash mismatch")
        value = json.loads(body)
        validate_manifest(value)
        if object_keys(value)["manifest"] != ref["key"]:
            raise ValueError("Manifest does not describe its immutable object key")
        values.append(value)
    return values


def run_stage(request, directory):
    from airline_warehouse.budget import live_budget
    from airline_warehouse.publication import claim, publish, request_result, reuse_active
    from airline_warehouse.warehouse import (
        build_candidate,
        candidate_plan,
        grant_candidate,
        processing_contract,
    )

    identity = os.environ.get("AIRLINE_CLOUD_IDENTITY")
    validate_request(request, identity)
    mode = request["mode"]
    deployment = request["deployment"]
    task = task_identity(deployment)
    if deployment["processing_contract"] != processing_contract():
        raise ValueError("Image processing contract differs from approved deployment")
    stage_seconds = 2700 if mode == "warehouse" else 300
    deadline = time.monotonic() + min(stage_seconds, request["deadline_epoch"] - time.time())
    os.environ["AIRLINE_CLOUD_REQUEST_ID"] = request["request_id"]
    s3 = sdk_factory("s3", 5)
    store = ReportStore(s3, identity, request["request_id"])
    # Create-only admission before SQL; lost acknowledgements cannot replay work.
    store.write(
        mode + "-intent.json",
        {
            "task_arn": task,
            "deployment": deployment,
            "request_sha256": hashlib.sha256(
                json.dumps(request, sort_keys=True).encode()
            ).hexdigest(),
        },
    )
    journal = store.journal(directory / "work.jsonl", deadline=deadline)
    journal.append(
        "stage_intent",
        mode=mode,
        target=request["target"],
        request_id=request["request_id"],
        deadline_epoch=request["deadline_epoch"],
    )
    budget = directory / "budget.json"
    budget.write_text(json.dumps(request["budget"]))
    extended = request["contract"] == "cloud-stage-request-v2"
    selection = (
        read_selection(s3, request["artifacts"])
        if extended
        else {"artifacts": request["artifacts"], "weather": None}
    )
    manifests = _manifests(s3, selection["artifacts"])
    plan = candidate_plan(manifests, "WORK_" + "0" * 24)
    if len(plan["inputs"]) == 36 and selection["weather"] is None:
        raise ValueError("Complete baseline requires its compatible fixed weather dependency")
    weather_path = None
    weather = None
    if selection["weather"] is not None and mode != "acquisition":
        weather_path = restore_weather(s3, selection["weather"], directory / "weather")
        from airline_warehouse.weather import read_weather

        weather, _ = read_weather(weather_path)
    input_binding = (
        {"inputs_sha256": selection_digest(plan["inputs"])}
        if extended
        else {"inputs": plan["inputs"]}
    )
    result = {
        "mode": mode,
        "request_id": request["request_id"],
        "target": request["target"],
        **input_binding,
    }
    if mode == "acquisition":
        # Explicit accepted-input selection, not a claim of new source acquisition.
        for m in manifests:
            head = s3.head_object(
                Bucket=BUCKET, Key=object_keys(m)["prepared"], ChecksumMode="ENABLED"
            )
            if (
                head.get("ServerSideEncryption") != "AES256"
                or head.get("ContentLength") != m["prepared_bytes"]
                or head.get("ChecksumSHA256")
                != base64.b64encode(bytes.fromhex(m["prepared_sha256"])).decode()
            ):
                raise ValueError("Accepted prepared object checksum/size/encryption changed")
        result.update(selection="ACCEPTED_IMMUTABLE_INPUTS", artifacts=request["artifacts"])
    elif mode == "warehouse":
        with connect_as("builder", deadline=deadline) as conn:
            with live_budget(
                conn,
                budget,
                deadline=deadline,
                work_id=request["request_id"],
                operation_seconds=2700,
            ) as remaining:
                bounded = tracked(conn, remaining, journal, "builder", deadline=deadline)
                for manifest in manifests:
                    execute_load(bounded, manifest, BUCKET, funding_verified=True)
        candidate = build_candidate(
            manifests,
            directory / "candidate",
            budget,
            journal=journal,
            whole_deadline=deadline,
            work_id=request["request_id"],
            weather_path=weather_path,
        )
        with connect_as("builder", deadline=deadline) as conn:
            with live_budget(
                conn, budget, deadline=deadline, work_id=request["request_id"]
            ) as remaining:
                grant_candidate(
                    tracked(conn, remaining, journal, "builder", deadline=deadline),
                    candidate,
                    "AIRLINE_PUBLISHER_ROLE",
                )
        if extended:
            result["candidate_reference"] = store.write_payload("candidate-payload.json", candidate)
        else:
            result["candidate"] = candidate
    else:
        with connect_as("publisher", deadline=deadline) as conn:
            with live_budget(
                conn,
                budget,
                deadline=deadline,
                work_id=request["request_id"],
                operation_seconds=300,
            ) as remaining:
                bounded = tracked(conn, remaining, journal, "publisher", deadline=deadline)
                if mode == "admit":
                    token = claim(
                        bounded,
                        request["target"],
                        request["request_id"],
                        attempt=request["request_id"],
                    )
                    if extended and token["status"] == "PUBLISHED":
                        descriptor = request_result(
                            bounded, request["target"], request["request_id"]
                        )
                    elif token["status"] != "RUNNING" or token["attempt"] != request["request_id"]:
                        raise ValueError("Existing request cannot silently launch another stage")
                    else:
                        descriptor = (
                            reuse_active(
                                bounded,
                                token,
                                plan["inputs"],
                                deployment["processing_contract"],
                                weather=weather,
                            )
                            if extended
                            else None
                        )
                    if extended and descriptor is not None:
                        if (
                            descriptor["inputs"] != plan["inputs"]
                            or descriptor["processing_contract"]
                            != deployment["processing_contract"]
                            or descriptor.get("weather") != weather
                        ):
                            raise ValueError(
                                "Replay request dependencies differ from committed result"
                            )
                        result.update(
                            reused=True,
                            descriptor_reference=store.write_payload(
                                "descriptor-payload.json", descriptor
                            ),
                        )
                    else:
                        result.update(authority=token, reused=False)
                else:
                    sealed = store.read(request["dependency"])
                    candidate = (
                        store.read_payload(sealed["candidate_reference"])
                        if extended
                        else sealed["candidate"]
                    )
                    if (
                        (
                            sealed.get("inputs_sha256") != selection_digest(plan["inputs"])
                            if extended
                            else sealed["inputs"] != plan["inputs"]
                        )
                        or sealed["request_id"] != request["request_id"]
                        or (extended and candidate.get("weather") != weather)
                    ):
                        raise ValueError("Sealed candidate belongs to different inputs/request")
                    descriptor = publish(
                        bounded,
                        request["authority"],
                        candidate,
                        request["request_id"],
                        timeout_seconds=min(300, remaining),
                    )
                    if extended:
                        result["descriptor_reference"] = store.write_payload(
                            "descriptor-payload.json", descriptor
                        )
                    else:
                        result["descriptor"] = descriptor
    result.update(
        status="COMPLETED", completed_epoch=int(time.time()), budget=json.loads(budget.read_text())
    )
    if time.time() > request["deadline_epoch"]:
        raise TimeoutError("Stage completed past its absolute deadline")
    reference = store.write(mode + "-report.json", result)
    control = {
        **deployment,
        "task_arn": task,
        "contract": "ecs-stage-result-v1",
        "request_id": request["request_id"],
        "target": request["target"],
        "stage": identity,
        "deadline_epoch": request["deadline_epoch"],
        **input_binding,
        "status": "COMPLETED",
        "completed_epoch": result["completed_epoch"],
        "output": reference,
    }
    return store.write(mode + ".json", control)


def main():
    logging.disable(logging.CRITICAL)

    def expired(signum, frame):
        raise TimeoutError("Cloud stage process deadline exhausted")

    try:
        raw = os.environ.get("AIRLINE_STAGE_REQUEST", "")
        if not 0 < len(raw.encode()) <= 65536:
            raise ValueError("Workflow request exceeds envelope bound")
        request = json.loads(raw)
        validate_request(request, os.environ.get("AIRLINE_CLOUD_IDENTITY"))
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(
            signal.ITIMER_REAL,
            min(
                2700 if request["mode"] == "warehouse" else 300,
                request["deadline_epoch"] - time.time(),
            ),
        )
        with tempfile.TemporaryDirectory(prefix="airline-stage-") as tmp:
            result = run_stage(request, Path(tmp))
        print(json.dumps({"status": "COMPLETED", "output": result}))
        return 0
    except Exception as error:
        # No normal success/failure handler may clear authority for unknown SQL.
        print(json.dumps({"status": "RECOVERY_REQUIRED", "error_type": type(error).__name__}))
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())

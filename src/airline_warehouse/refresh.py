"""Finite local prepared-artifact -> load -> dbt -> frozen release runner.

No acquisition, scheduling, automatic retry, takeover or administrative fallback.
"""

import json
import time
import uuid
from pathlib import Path

from airline_warehouse.analytics import relation
from airline_warehouse.budget import live_budget, mark_recovery
from airline_warehouse.connection import connect_as
from airline_warehouse.execution import WorkJournal, producer_lock, tracked
from airline_warehouse.load import execute_load, read_artifact
from airline_warehouse.publication import (
    Busy,
    CommitUnknown,
    claim,
    publish,
    reconcile,
    request_result,
    retire,
    reuse_active,
)
from airline_warehouse.warehouse import (
    BUCKET,
    RecoveryRequired,
    build_candidate,
    candidate_plan,
    grant_candidate,
    processing_contract,
)


def _record_uncertainty(output, budget_path, request_id, release_id, error):
    if budget_path.exists():
        mark_recovery(budget_path, uncertain_request=request_id)
    (output / "failure.json").write_text(
        json.dumps(
            {
                "status": "RECOVERY_REQUIRED",
                "error_type": type(error).__name__,
                "request_id": request_id,
                "release_id": release_id,
            }
        )
        + "\n"
    )


def refresh(
    artifacts,
    output,
    budget_path,
    target,
    request_id,
    *,
    stage="full",
    candidate_path=None,
    weather_path=None,
):
    """Full loads inputs and builds; build skips loading; publish uses a sealed dependency.

    A matching active input map and processing contract returns the same release.
    Output is create-only; persist intent before any authority/warehouse operation.
    Initialization is a separate attended migration, not a hidden refresh side effect.
    """
    if stage not in ("full", "build", "publish"):
        raise ValueError("Unknown stage; choose full, build or publish")
    if stage == "publish" and (candidate_path is None or not Path(candidate_path).is_file()):
        raise ValueError("Publish rerun requires an existing sealed candidate dependency")
    manifests = [read_artifact(Path(p)) for p in artifacts]
    plan = candidate_plan(manifests, "WORK_" + "0" * 24)
    contract = processing_contract()
    weather = None
    if weather_path is not None:
        from airline_warehouse.weather import read_weather

        weather, _ = read_weather(weather_path)
    candidate = None
    if stage == "publish":
        candidate = json.loads(Path(candidate_path).read_text())
        relation(candidate, development=True)
        dependency = candidate_plan(manifests, candidate["schema"])
        if (
            any(candidate.get(k) != v for k, v in dependency.items())
            or candidate.get("processing_contract") != contract
            or candidate.get("weather") != weather
        ):
            raise ValueError("Candidate dependency is incompatible with selected inputs/processing")
    output, budget_path = Path(output), Path(budget_path)
    output.mkdir(parents=True, exist_ok=False)
    release_id = uuid.uuid4().hex
    attempt = uuid.uuid4().hex
    intent = dict(
        target=target,
        request_id=request_id,
        release_id=release_id,
        stage=stage,
        inputs=plan["inputs"],
        processing_contract=contract,
        attempt=attempt,
        weather=weather,
    )
    (output / "intent.json").write_text(json.dumps(intent, indent=2) + "\n")
    journal = WorkJournal(output / "work.jsonl")
    producer = producer_lock(journal.path)
    producer.__enter__()
    whole_deadline = time.monotonic() + 2700
    token = None
    try:
        with (
            connect_as("publisher", deadline=whole_deadline) as publisher,
            live_budget(
                publisher, budget_path, deadline=whole_deadline, work_id=request_id
            ) as remaining,
        ):
            publisher = tracked(publisher, remaining, journal, "publisher")
            token = claim(publisher, target, request_id, attempt=attempt)
            (output / "authority.json").write_text(json.dumps(token) + "\n")
            if token["status"] == "RUNNING" and token["attempt"] != attempt:
                token = None
                raise Busy("Request already running; duplicate does not own data-work authority")
            if token["status"] != "RUNNING":
                descriptor = request_result(publisher, target, request_id)
                if (
                    descriptor["inputs"] != plan["inputs"]
                    or descriptor["processing_contract"] != contract
                    or descriptor.get("weather") != weather
                ):
                    raise ValueError("Duplicate request identity has different dependencies")
            else:
                descriptor = reuse_active(
                    publisher, token, plan["inputs"], contract, weather=weather
                )
        if descriptor is not None:
            result = dict(status="PUBLISHED", reused=True, descriptor=descriptor)
        else:
            with (
                connect_as("builder", deadline=whole_deadline) as builder,
                live_budget(
                    builder,
                    budget_path,
                    deadline=whole_deadline,
                    work_id=request_id,
                    operation_seconds=2700,
                ) as remaining,
            ):
                bounded = tracked(builder, remaining, journal, "builder")
                if stage == "full":
                    for manifest in manifests:
                        execute_load(bounded, manifest, BUCKET, funding_verified=True)
            if candidate is None:
                candidate = build_candidate(
                    manifests,
                    output / "candidate",
                    budget_path,
                    weather_path=weather_path,
                    journal=journal,
                    whole_deadline=whole_deadline,
                    work_id=request_id,
                )
            with (
                connect_as("builder", deadline=whole_deadline) as builder,
                live_budget(
                    builder, budget_path, deadline=whole_deadline, work_id=request_id
                ) as remaining,
            ):
                grant_candidate(
                    tracked(builder, remaining, journal, "builder"),
                    candidate,
                    "AIRLINE_PUBLISHER_ROLE",
                )
            (output / "candidate-reference.json").write_text(json.dumps(candidate, indent=2) + "\n")
            with (
                connect_as("publisher", deadline=whole_deadline) as publisher,
                live_budget(
                    publisher, budget_path, deadline=whole_deadline, work_id=request_id
                ) as remaining,
            ):
                deadline = time.monotonic() + remaining
                publisher = tracked(publisher, remaining, journal, "publisher", deadline=deadline)
                try:
                    descriptor = publish(
                        publisher,
                        token,
                        candidate,
                        release_id,
                        timeout_seconds=min(300, remaining),
                        evidence_path=output / "publication-queries.jsonl",
                    )
                except CommitUnknown:
                    try:
                        with connect_as("publisher", deadline=deadline) as fresh:
                            descriptor = reconcile(
                                tracked(fresh, remaining, journal, "publisher", deadline=deadline),
                                token,
                                release_id,
                            )
                    except BaseException as error:
                        raise RecoveryRequired(
                            "Publication outcome needs attended reconciliation"
                        ) from error
            result = dict(status="PUBLISHED", reused=False, descriptor=descriptor)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except ValueError:
        # Only known synchronous validation failures retire authority. Busy/stale duplicate
        # requests must not retire someone else's generation.
        if token is not None and token.get("status") == "RUNNING":
            try:
                with (
                    connect_as("publisher", deadline=whole_deadline) as publisher,
                    live_budget(
                        publisher, budget_path, deadline=whole_deadline, work_id=request_id
                    ) as remaining,
                ):
                    retire(tracked(publisher, remaining, journal, "publisher"), token, "FAILED")
            except BaseException as error:
                _record_uncertainty(output, budget_path, request_id, release_id, error)
                raise RecoveryRequired(
                    "Failed-run authority retirement needs reconciliation"
                ) from error
        (output / "failure.json").write_text('{"status":"FAILED"}\n')
        raise
    except BaseException as error:
        _record_uncertainty(output, budget_path, request_id, release_id, error)
        raise
    finally:
        producer.__exit__(None, None, None)

"""Single-operator batch accounting, not a billing cap or recovery watchdog."""

import fcntl
import json
import math
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from airline_warehouse.load import check_account_monitor


@contextmanager
def live_budget(
    connection, state_path: Path, *, deadline=None, work_id=None, operation_seconds=600
):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Batch budget already active in another local process") from error
        try:
            with _accounted_budget(
                connection,
                path,
                deadline=deadline,
                work_id=work_id,
                operation_seconds=operation_seconds,
            ) as remaining:
                yield remaining
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def _accounted_budget(
    connection, state_path: Path, *, deadline=None, work_id=None, operation_seconds=600
):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = (
        json.loads(path.read_text())
        if path.exists()
        else {"baseline_credits": "0.12", "elapsed_seconds": 0, "operations": []}
    )
    if state.get("recovery_required") or state.get("operation_active"):
        raise ValueError(
            "Unknown prior work requires attended reconciliation before another live operation"
        )
    elapsed = state.get("elapsed_seconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Corrupt batch accounting; inspect rather than reset the budget")
    # Historical ledgers retain their original allowance. Explicit newer ledgers
    # may use the existing account monitor with a recovery reserve instead of an
    # invented batch credit/time cap. Every individual operation remains finite.
    maximum = state.get("max_elapsed_seconds", 2700)
    if not 1 <= operation_seconds <= 2700:
        raise ValueError("Operation must fit the reviewed warehouse-stage bound")
    remaining = operation_seconds if maximum is None else maximum - state["elapsed_seconds"]
    if remaining <= 0:
        raise ValueError("Approved 45-minute live-work budget exhausted")
    if deadline is not None:
        remaining = min(remaining, deadline - time.monotonic())
        if remaining < 1:
            raise TimeoutError("Whole-run absolute deadline exhausted")
    with connection.cursor() as cur:
        cur.execute("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
        names = [c[0].lower() for c in cur.description]
        monitors = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        if len(monitors) != 1:
            raise ValueError("Account monitor is unavailable")
        monitor = monitors[0]
        check_account_monitor(monitor)
        credit_limit = state.get("additional_credit_limit", "2")
        if credit_limit is not None and (
            Decimal(str(monitor["used_credits"])) - Decimal(state["baseline_credits"])
            >= Decimal(str(credit_limit))
        ):
            raise ValueError("Approved two additional observed-credit budget exhausted")
        reserve = Decimal(str(state.get("recovery_reserve_credits", "0")))
        if Decimal(str(monitor["remaining_credits"])) <= reserve:
            raise ValueError("Account monitor recovery reserve reached; no new workload")
        state["last_observed_credits"] = str(monitor["used_credits"])
        cur.execute("SHOW WAREHOUSES LIKE 'AIRLINE_DEV_WH'")
        names = [c[0].lower() for c in cur.description]
        warehouses = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        if (
            len(warehouses) != 1
            or warehouses[0]["size"] != "X-Small"
            or (
                str(warehouses[0]["enable_query_acceleration"]).lower() != "false"
                or not 0 < int(warehouses[0]["auto_suspend"]) <= 60
            )
        ):
            raise ValueError("Warehouse safeguards differ from approved limits")
    start = time.monotonic()
    state["operation_active"] = True
    state["active_work"] = work_id
    state["operation_started_at"] = time.time()
    path.write_text(json.dumps(state, indent=2) + "\n")
    try:
        yield min(remaining, operation_seconds)
    except BaseException as error:
        if not isinstance(error, ValueError):
            state.update(recovery_required=True, uncertain_error_type=type(error).__name__)
            state["recovery_work"] = work_id
        raise
    finally:
        state["elapsed_seconds"] += time.monotonic() - start
        state.pop("operation_active", None)
        state.pop("active_work", None)
        state.pop("operation_started_at", None)
        state["operations"].append({"elapsed_seconds": time.monotonic() - start})
        path.write_text(json.dumps(state, indent=2) + "\n")


def mark_recovery(state_path: Path, **details):
    """Enrich a blocked operation under the same lock; never overwrite another writer."""
    path = Path(state_path)
    with Path(str(path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text())
        state.update(recovery_required=True, **details)
        path.write_text(json.dumps(state, indent=2) + "\n")


@contextmanager
def attended_budget_recovery(state_path: Path, work_id):
    """Own ledger scope/accounting and serialize proof-backed attended admission."""
    path = Path(state_path)
    with Path(str(path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(path.read_text())
        blocked = state.get("recovery_required") or state.get("operation_active")
        if blocked and work_id not in (
            state.get("active_work"),
            state.get("recovery_work"),
            state.get("uncertain_request"),
        ):
            raise ValueError("Budget uncertainty belongs to different/unidentified work")

        def complete(proof_path):
            proof = json.loads(Path(proof_path).read_text())
            if (
                proof.get("request_id") != work_id
                or proof.get("execution") != "TERMINAL"
                or proof.get("cleanup") != "COMPLETE"
            ):
                raise ValueError("Matching durable terminal proof required before admission")
            if state.get("operation_active"):
                start = state.get("operation_started_at")
                if start is None:
                    raise ValueError("Interrupted operation has no accounting start; no reset")
                state["elapsed_seconds"] += max(0, time.time() - start)
            for key in (
                "recovery_required",
                "operation_active",
                "active_work",
                "recovery_work",
                "uncertain_request",
                "uncertain_error_type",
                "operation_started_at",
            ):
                state.pop(key, None)
            state.setdefault("recoveries", []).append(str(proof_path))
            path.write_text(json.dumps(state, indent=2) + "\n")

        yield complete

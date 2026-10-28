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
def live_budget(connection, state_path: Path):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Batch budget already active in another local process") from error
        try:
            with _accounted_budget(connection, path) as remaining:
                yield remaining
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def _accounted_budget(connection, state_path: Path):
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
    remaining = 2700 - state["elapsed_seconds"]
    if remaining <= 0:
        raise ValueError("Approved 45-minute live-work budget exhausted")
    with connection.cursor() as cur:
        cur.execute("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
        names = [c[0].lower() for c in cur.description]
        monitors = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        if len(monitors) != 1:
            raise ValueError("Account monitor is unavailable")
        monitor = monitors[0]
        check_account_monitor(monitor)
        if Decimal(str(monitor["used_credits"])) - Decimal(state["baseline_credits"]) >= 2:
            raise ValueError("Approved two additional observed-credit budget exhausted")
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
    path.write_text(json.dumps(state, indent=2) + "\n")
    try:
        yield min(remaining, 600)
    except BaseException as error:
        if not isinstance(error, ValueError):
            state.update(recovery_required=True, uncertain_error_type=type(error).__name__)
        raise
    finally:
        state["elapsed_seconds"] += time.monotonic() - start
        state.pop("operation_active", None)
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

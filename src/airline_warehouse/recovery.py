"""Attended originating-identity recovery; no watcher, takeover or broad canceller."""

import json
import time
import uuid
from pathlib import Path

from airline_warehouse.budget import attended_budget_recovery
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.execution import producer_lock

TERMINAL = {"SUCCESS", "FAILED_WITH_ERROR", "FAILED_WITH_INCIDENT", "ABORTED"}


def recover_local(output, budget_path):
    """Prove local exclusion, stop exact own sessions, reconcile, then retire matching work.

    Any unsupported/unknown query/session/transaction status leaves authority and
    budget blocked. Missing history/list entries are never termination evidence.
    """
    output, budget_path = Path(output), Path(budget_path)
    journal_path = output / "work.jsonl"
    with producer_lock(journal_path, recovery=True):
        if not (output / "intent.json").is_file():
            raise ValueError("Missing durable intent; inspect rather than infer recovery scope")
        intent = json.loads((output / "intent.json").read_text())
        with attended_budget_recovery(budget_path, intent["request_id"]) as complete:
            if not journal_path.exists():
                raise ValueError(
                    "No work journal; unknown submissions require explicit investigation"
                )
            events = [json.loads(line) for line in journal_path.read_text().splitlines()]
            sessions = {}
            for e in events:
                if e["event"] == "session":
                    old = sessions.setdefault(e["session_id"], e["identity"])
                    if old != e["identity"] or old not in ("builder", "publisher"):
                        raise ValueError("Conflicting originating session identity")
            if any(
                e.get("session_id") not in sessions for e in events if e["event"] == "query_intent"
            ):
                raise ValueError("Unregistered submission; cannot establish originating identity")
            deadline = time.monotonic() + 300
            proofs = []
            for sid, identity in sessions.items():
                with connect_as(identity, deadline=deadline) as conn:
                    bounded = DeadlineConnection(conn, 300, deadline=deadline)
                    with bounded.cursor() as cur:
                        # Own-session abort closes even a lost query-ID/BEGIN interval.
                        cur.execute("SELECT SYSTEM$ABORT_SESSION(%s)", (int(sid),))
                        acknowledgment = cur.fetchone()[0]
                        if "terminated" not in str(acknowledgment).lower():
                            raise ValueError("Exact session termination not acknowledged")
                    query_ids = {
                        e["query_id"]
                        for e in events
                        if e["event"] == "query_result"
                        and e["session_id"] == sid
                        and e.get("query_id")
                    }
                    for qid in query_ids:
                        while True:
                            status = conn.get_query_status(qid).name
                            if status in TERMINAL:
                                break
                            if status in ("NO_DATA", "DISCONNECTED"):
                                raise ValueError("Query termination is not proven")
                            if time.monotonic() + 1 >= deadline:
                                raise TimeoutError("Scoped termination verification deadline")
                            time.sleep(0.2)
                    proofs.append(
                        {
                            "session_id": sid,
                            "identity": identity,
                            "termination": acknowledgment,
                            "terminal_queries": sorted(query_ids),
                        }
                    )
            result = {
                "execution": "TERMINAL",
                "publication": "NONE",
                "cleanup": "COMPLETE",
                "request_id": intent["request_id"],
                "proofs": proofs,
            }
            if intent.get("target"):
                from airline_warehouse.publication import recover_terminal_authority

                with connect_as("publisher", deadline=deadline) as publisher:
                    descriptor = recover_terminal_authority(
                        DeadlineConnection(publisher, 300, deadline=deadline), intent
                    )
                result["publication"] = "PUBLISHED" if descriptor else "NOT_PUBLISHED"
                if descriptor:
                    result["descriptor"] = descriptor
            # Preserve proof BEFORE making local admission possible again. A lost
            # final write/commit is reconciled by repeating this attended operation.
            proof_path = output / ("recovery-" + uuid.uuid4().hex + ".json")
            proof_path.write_text(json.dumps(result, indent=2) + "\n")
            complete(proof_path)
            return result

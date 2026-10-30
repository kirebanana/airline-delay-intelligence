"""One decreasing server/client SQL deadline, including dbt's child connections."""

import json
import re
import time
from contextlib import contextmanager
from pathlib import Path


def execute_bounded(execute, deadline, sql, *args, **kwargs):
    remaining = int(deadline - time.monotonic())
    if sql.strip().upper() == "ROLLBACK":
        remaining = max(remaining, 5)  # always permit bounded lock-release cleanup
    elif remaining < 1:
        raise TimeoutError("Absolute SQL deadline exhausted")
    remaining = min(remaining, 600)  # never raise the existing server statement ceiling
    execute(
        f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS={remaining}, "
        f"STATEMENT_QUEUED_TIMEOUT_IN_SECONDS={min(60, remaining)}, "
        f"LOCK_TIMEOUT={min(5, remaining)}",
        timeout=remaining,
    )
    # Configuration round trips spend the same budget. Carry the freshly derived
    # server limits with the workload itself (documented connector query params),
    # not just the earlier ALTER SESSION. Never submit after configuration expiry.
    remaining = int(deadline - time.monotonic())
    if sql.strip().upper() == "ROLLBACK":
        remaining = max(remaining, 5)
    elif remaining < 1:
        raise TimeoutError("Absolute SQL deadline exhausted during configuration")
    remaining = min(remaining, 600)
    # Existing loader/dbt hooks cannot restore a larger static limit.
    sql = re.sub(
        r"\b(STATEMENT_TIMEOUT_IN_SECONDS|STATEMENT_QUEUED_TIMEOUT_IN_SECONDS|"
        r"LOCK_TIMEOUT)\s*=\s*(\d+)",
        lambda m: f"{m[1]}={min(int(m[2]) or remaining, remaining)}",
        sql,
        flags=re.I,
    )
    kwargs["timeout"] = min(kwargs.get("timeout") or remaining, remaining)
    parameters = dict(kwargs.get("_statement_params") or {})
    for name, ceiling in (
        ("STATEMENT_TIMEOUT_IN_SECONDS", remaining),
        ("STATEMENT_QUEUED_TIMEOUT_IN_SECONDS", min(60, remaining)),
        ("LOCK_TIMEOUT", min(5, remaining)),
    ):
        parameters[name] = min(int(parameters.get(name, ceiling)) or ceiling, ceiling)
    kwargs["_statement_params"] = parameters
    return execute(sql, *args, **kwargs)


class DeadlineConnection:
    def __init__(
        self,
        connection,
        seconds,
        evidence_path=None,
        *,
        deadline=None,
        journal=None,
        session_id=None,
    ):
        self.connection = connection
        self.deadline = deadline if deadline is not None else time.monotonic() + seconds
        self.evidence_path = evidence_path
        self.journal, self.session_id = journal, session_id
        if isinstance(connection, DeadlineConnection):
            self.connection = connection.connection
            self.deadline = min(self.deadline, connection.deadline)
            self.evidence_path = evidence_path or connection.evidence_path
            self.journal = journal or connection.journal
            self.session_id = session_id or connection.session_id

    @contextmanager
    def cursor(self):
        with self.connection.cursor() as cur:
            yield _Cursor(cur, self.deadline, self.evidence_path, self.journal, self.session_id)


class _Cursor:
    def __init__(self, cursor, deadline, evidence_path, journal=None, session_id=None):
        self.cursor, self.deadline, self.evidence_path = cursor, deadline, evidence_path
        self.journal, self.session_id = journal, session_id

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, *args, **kwargs):
        try:
            execute = self.cursor.execute
            if self.journal is not None:

                def execute(command, *a, **kw):
                    return self.journal.execute(
                        self.cursor.execute, self.cursor, self.session_id, command, *a, **kw
                    )

            execute_bounded(execute, self.deadline, sql, *args, **kwargs)
        finally:
            if self.evidence_path is not None:
                with Path(self.evidence_path).open("a") as stream:
                    stream.write(
                        json.dumps({"query_id": self.cursor.sfqid, "operation": sql.split()[0]})
                        + "\n"
                    )
        return self

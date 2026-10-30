"""Durable secret-free own-work journal and local producer/recovery exclusion."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def producer_lock(journal_path, *, recovery=False):
    path = Path(str(journal_path) + ".producers.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, (fcntl.LOCK_EX if recovery else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("A local producer/recovery still owns this attempt") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class WorkJournal:
    def __init__(self, path):
        self.path = Path(path)

    def append(self, event, **fields):
        record = {"event": event, "at": time.time(), "pid": os.getpid(), **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def session(self, connection, identity):
        if identity not in ("builder", "publisher"):
            raise ValueError("Journal only originating workload identities")
        session = connection.session_id
        self.append("session", session_id=session, identity=identity)
        return session

    def execute(self, execute, cursor, session_id, sql, *args, **kwargs):
        statement = uuid.uuid4().hex
        self.append(
            "query_intent",
            statement=statement,
            session_id=session_id,
            operation=sql.split()[0].upper(),
            sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        )
        previous = getattr(cursor, "sfqid", None)
        returned = False
        try:
            result = execute(sql, *args, **kwargs)
            returned = True
            return result
        finally:
            query_id = getattr(cursor, "sfqid", None)
            self.append(
                "query_result",
                statement=statement,
                session_id=session_id,
                query_id=query_id if query_id != previous else None,
                returned=returned,
            )


def tracked(connection, seconds, journal, identity, *, deadline=None):
    from airline_warehouse.deadlines import DeadlineConnection

    session = journal.session(connection, identity)
    return DeadlineConnection(
        connection, seconds, deadline=deadline, journal=journal, session_id=session
    )


def run_dbt_child(command, env, output, deadline, journal):
    """Finite child group with a ready/go handshake under the producer lock.

    A child launched immediately before parent death cannot submit SQL unless it
    already holds the shared producer lock. Recovery takes that lock exclusively.
    Killing the group proves only local termination, never detached SQL termination.
    """
    ready, go = output / "child-ready", output / "child-go"
    env.update(
        AIRLINE_WORK_JOURNAL=str(journal.path.resolve()),
        AIRLINE_CHILD_READY=str(ready),
        AIRLINE_CHILD_GO=str(go),
    )
    journal.append("child_launch_intent")
    with (output / "build.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        journal.append("child", child_pid=process.pid, process_group=process.pid)
        try:
            handshake_deadline = min(deadline, time.monotonic() + 15)
            while not ready.exists() and process.poll() is None:
                if time.monotonic() >= handshake_deadline:
                    raise TimeoutError("dbt producer handshake deadline")
                time.sleep(0.05)
            if ready.exists():
                go.write_text(str(process.pid))
            return process.wait(timeout=max(0.01, deadline - time.monotonic()))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            journal.append("child_terminal", child_pid=process.pid, returncode=process.returncode)

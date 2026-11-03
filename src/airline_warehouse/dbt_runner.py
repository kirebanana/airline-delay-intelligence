"""Dedicated dbt child process: clamp every connector statement to one deadline.

The adapter has no per-statement absolute-deadline profile setting. Instrument its
external Snowflake driver only inside this finite subprocess, never in the dashboard.
"""

import os
import sys
import time
from pathlib import Path

from airline_warehouse.deadlines import execute_bounded
from airline_warehouse.execution import WorkJournal, producer_lock


def _run(journal):
    import snowflake.connector
    from dbt.cli.main import dbtRunner
    from snowflake.connector.cursor import SnowflakeCursor

    deadline = float(os.environ["AIRLINE_DBT_DEADLINE"])
    original_execute = SnowflakeCursor.execute
    original_connect = snowflake.connector.connect

    def execute(cursor, command, *args, **kwargs):
        return execute_bounded(
            lambda sql, *a, **kw: journal.execute(
                lambda sql, *a, **kw: original_execute(cursor, sql, *a, **kw),
                cursor,
                cursor.connection.session_id,
                sql,
                *a,
                **kw,
            ),
            deadline,
            command,
            *args,
            **kwargs,
        )

    def connect(**kwargs):
        remaining = int(deadline - time.monotonic())
        if remaining < 1:
            raise TimeoutError("dbt connection deadline exhausted")
        if "AIRLINE_CLOUD_IDENTITY" in os.environ:
            from airline_warehouse.cloud_identity import dbt_parameters

            kwargs = dbt_parameters(kwargs, os.environ["AIRLINE_CLOUD_IDENTITY"], deadline=deadline)
        kwargs.update(
            login_timeout=min(15, remaining),
            network_timeout=min(30, remaining),
            socket_timeout=min(30, remaining),
        )
        connection = original_connect(**kwargs)
        journal.session(connection, "builder")
        if "AIRLINE_CLOUD_IDENTITY" in os.environ:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("USE SECONDARY ROLES NONE")
                    cursor.execute(
                        "SELECT CURRENT_ACCOUNT(),CURRENT_REGION(),CURRENT_ROLE(),CURRENT_USER()"
                    )
                    if cursor.fetchone() != (
                        "DC50202",
                        "AWS_US_EAST_2",
                        "AIRLINE_DEV_ROLE",
                        "AIRLINE_DEV",
                    ):
                        raise ValueError("dbt connected to unexpected workload identity")
            except BaseException:
                connection.close()
                raise
        return connection

    SnowflakeCursor.execute = execute
    snowflake.connector.connect = connect
    result = dbtRunner().invoke(sys.argv[1:])
    return 0 if result.success else 1


def main():
    if "AIRLINE_CLOUD_IDENTITY" in os.environ:
        from airline_warehouse.cloud_artifacts import ReportStore
        from airline_warehouse.connectivity_probe import sdk_factory

        if os.environ["AIRLINE_CLOUD_IDENTITY"] != "warehouse":
            raise ValueError("Only warehouse task may execute dbt")
        store = ReportStore(
            sdk_factory("s3", 5), "warehouse", os.environ["AIRLINE_CLOUD_REQUEST_ID"]
        )
        journal = store.journal(
            os.environ["AIRLINE_WORK_JOURNAL"], deadline=float(os.environ["AIRLINE_DBT_DEADLINE"])
        )
    else:
        journal = WorkJournal(os.environ["AIRLINE_WORK_JOURNAL"])
    with producer_lock(journal.path):
        Path(os.environ["AIRLINE_CHILD_READY"]).write_text(str(os.getpid()))
        handshake_deadline = min(float(os.environ["AIRLINE_DBT_DEADLINE"]), time.monotonic() + 15)
        go = Path(os.environ["AIRLINE_CHILD_GO"])
        while not go.exists():
            if time.monotonic() >= handshake_deadline:
                raise TimeoutError("Parent never authorized child data work")
            time.sleep(0.05)
        if go.read_text() != str(os.getpid()):
            raise ValueError("Child handshake identity mismatch")
        return _run(journal)


if __name__ == "__main__":
    raise SystemExit(main())

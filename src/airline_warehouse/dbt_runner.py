"""Dedicated dbt child process: clamp every connector statement to one deadline.

The adapter has no per-statement absolute-deadline profile setting. Instrument its
external Snowflake driver only inside this finite subprocess, never in the dashboard.
"""

import os
import sys
import time

from airline_warehouse.deadlines import execute_bounded


def main():
    import snowflake.connector
    from dbt.cli.main import dbtRunner
    from snowflake.connector.cursor import SnowflakeCursor

    deadline = float(os.environ["AIRLINE_DBT_DEADLINE"])
    original_execute = SnowflakeCursor.execute
    original_connect = snowflake.connector.connect

    def execute(cursor, command, *args, **kwargs):
        return execute_bounded(
            lambda sql, *a, **kw: original_execute(cursor, sql, *a, **kw),
            deadline,
            command,
            *args,
            **kwargs,
        )

    def connect(**kwargs):
        remaining = int(deadline - time.monotonic())
        if remaining < 1:
            raise TimeoutError("dbt connection deadline exhausted")
        kwargs.update(
            login_timeout=min(15, remaining),
            network_timeout=min(30, remaining),
            socket_timeout=min(30, remaining),
        )
        return original_connect(**kwargs)

    SnowflakeCursor.execute = execute
    snowflake.connector.connect = connect
    result = dbtRunner().invoke(sys.argv[1:])
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

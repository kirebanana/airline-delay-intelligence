"""Reuse the existing named Snowflake CLI key-pair identity without secret copying."""

import os
import re
import stat
import time
import tomllib
from pathlib import Path

from airline_warehouse.deadlines import DeadlineConnection


def _cloud_connection(kind, query_tag, deadline):
    from airline_warehouse.cloud_identity import SECRETS, private_key

    key = private_key(kind, os.environ["AIRLINE_CLOUD_IDENTITY"], deadline=deadline)
    _, _, _, user, role = SECRETS[kind]
    conn = _login(
        dict(
            account="LMOOEWP-DQ15927",
            user=user,
            role=role,
            database="AIRLINE_DB",
            warehouse="AIRLINE_DEV_WH",
            authenticator="SNOWFLAKE_JWT",
            private_key=key,
            session_parameters={
                "STATEMENT_TIMEOUT_IN_SECONDS": 600,
                "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 60,
                "LOCK_TIMEOUT": 5,
                "QUERY_TAG": query_tag,
            },
        ),
        deadline,
    )
    try:
        with DeadlineConnection(conn, 600, deadline=deadline).cursor() as cur:
            cur.execute("USE SECONDARY ROLES NONE")
            cur.execute("SELECT CURRENT_ACCOUNT(),CURRENT_REGION(),CURRENT_ROLE(),CURRENT_USER()")
            if cur.fetchone() != ("DC50202", "AWS_US_EAST_2", role, user):
                raise ValueError("Unexpected workload account/region/role/user")
    except BaseException:
        conn.close()
        raise
    return conn


def _login(params, deadline):
    import snowflake.connector
    from snowflake.connector.errors import OperationalError

    # Only pre-return login transport failures retry; never replay workload SQL.
    if deadline is None:
        deadline = time.monotonic() + 30
    for attempt in range(2):
        remaining = int(deadline - time.monotonic())
        if remaining < 1:
            raise TimeoutError("Connection absolute deadline exhausted")
        params.update(
            login_timeout=min(15, remaining),
            network_timeout=min(30, remaining),
            socket_timeout=min(30, remaining),
        )
        try:
            return snowflake.connector.connect(**params)
        except OperationalError as error:
            if attempt or error.errno not in (250001, 250003):
                raise


def connect(query_tag="airline:raw-ingest:v1", *, deadline=None):
    if not re.fullmatch(r"airline:[A-Za-z0-9:_-]{1,120}", query_tag):
        raise ValueError("Query tag must be a bounded project identifier")
    if "AIRLINE_CLOUD_IDENTITY" in os.environ:
        return _cloud_connection("builder", query_tag, deadline)
    path = Path.home() / ".snowflake/config.toml"
    config = tomllib.loads(path.read_text())["connections"]["airline"]
    expected = {
        "account": "LMOOEWP-DQ15927",
        "user": "AIRLINE_DEV",
        "role": "AIRLINE_DEV_ROLE",
        "database": "AIRLINE_DB",
        "warehouse": "AIRLINE_DEV_WH",
        "authenticator": "SNOWFLAKE_JWT",
    }
    if any(config.get(k, "").upper() != v for k, v in expected.items()):
        raise ValueError("Named connection is not the approved project service identity")
    key = Path(config["private_key_file"]).expanduser()
    if stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise ValueError("Private key must not be group/world accessible")
    params = {
        **expected,
        "private_key_file": str(key),
        "login_timeout": 15,
        "network_timeout": 30,
        "socket_timeout": 30,
        "session_parameters": {
            "STATEMENT_TIMEOUT_IN_SECONDS": 600,
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 60,
            "LOCK_TIMEOUT": 10,
            "QUERY_TAG": query_tag,
        },
    }
    # Never print/serialize credentials or passphrases. No admin role fallback.
    if "AIRLINE_KEY_PASSPHRASE" in os.environ:
        params["private_key_file_pwd"] = os.environ["AIRLINE_KEY_PASSPHRASE"]
    conn = _login(params, deadline)
    with DeadlineConnection(conn, 600, deadline=deadline).cursor() as cur:
        cur.execute("USE SECONDARY ROLES NONE")
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()")
        if cur.fetchone() != ("DC50202", "AWS_US_EAST_2", "AIRLINE_DEV_ROLE"):
            conn.close()
            raise ValueError("Connected to unexpected account, region or role")
    return conn


def connect_as(kind: str, *, deadline=None):
    """Separate service identities; never let a caller select an arbitrary role."""
    if "AIRLINE_CLOUD_IDENTITY" in os.environ:
        return _cloud_connection(kind, "airline:cloud:" + kind, deadline)
    if kind == "builder":
        return connect("airline:batch05-10:builder", deadline=deadline)
    if kind not in ("publisher", "reader"):
        raise ValueError("Unknown workload identity")
    name = "AIRLINE_" + kind.upper()
    key = Path.home() / ".snowflake/airline-analytics" / (kind + ".p8")
    if stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise ValueError("Workload key must be owner-only")
    conn = _login(
        dict(
            account="LMOOEWP-DQ15927",
            user=name,
            role=name + "_ROLE",
            database="AIRLINE_DB",
            warehouse="AIRLINE_DEV_WH",
            authenticator="SNOWFLAKE_JWT",
            private_key_file=str(key),
            login_timeout=15,
            network_timeout=30,
            socket_timeout=30,
            session_parameters={
                "STATEMENT_TIMEOUT_IN_SECONDS": 600,
                "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 60,
                "LOCK_TIMEOUT": 5,
                "QUERY_TAG": "airline:batch05-10:" + kind,
            },
        ),
        deadline,
    )
    with DeadlineConnection(conn, 600, deadline=deadline).cursor() as cur:
        cur.execute("USE SECONDARY ROLES NONE")
        cur.execute("SELECT CURRENT_ACCOUNT(),CURRENT_REGION(),CURRENT_ROLE(),CURRENT_USER()")
        if cur.fetchone() != ("DC50202", "AWS_US_EAST_2", name + "_ROLE", name):
            conn.close()
            raise ValueError("Unexpected workload account/role/user")
    return conn

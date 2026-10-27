"""Reuse the existing named Snowflake CLI key-pair identity without secret copying."""

import os
import stat
import tomllib
from pathlib import Path


def connect():
    import snowflake.connector

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
            "QUERY_TAG": "airline:raw-ingest:v1",
        },
    }
    # Never print/serialize credentials or passphrases. No admin role fallback.
    if "AIRLINE_KEY_PASSPHRASE" in os.environ:
        params["private_key_file_pwd"] = os.environ["AIRLINE_KEY_PASSPHRASE"]
    conn = snowflake.connector.connect(**params)
    with conn.cursor() as cur:
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()")
        if cur.fetchone() != ("DC50202", "AWS_US_EAST_2", "AIRLINE_DEV_ROLE"):
            conn.close()
            raise ValueError("Connected to unexpected account, region or role")
    return conn

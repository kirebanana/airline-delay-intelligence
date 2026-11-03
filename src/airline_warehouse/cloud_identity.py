"""Exact workload identity -> pinned Secrets Manager key, never operator fallback."""

import json
import time

SECRETS = {
    "builder": (
        "warehouse",
        "arn:aws:secretsmanager:us-east-2:336805808138:secret:airline-delay-intelligence/snowflake/warehouse-Hcg4iF",
        "be15541a-9e70-44bb-912a-220129a44001",
        "AIRLINE_DEV",
        "AIRLINE_DEV_ROLE",
    ),
    "publisher": (
        "publisher",
        "arn:aws:secretsmanager:us-east-2:336805808138:secret:airline-delay-intelligence/snowflake/publisher-m6I7eB",
        "be15541a-9e70-44bb-912a-220129a44002",
        "AIRLINE_PUBLISHER",
        "AIRLINE_PUBLISHER_ROLE",
    ),
}


def dbt_parameters(params, cloud_kind, *, deadline):
    """Clamp dbt's external driver boundary to the sole warehouse identity."""
    expected = {
        "account": "LMOOEWP-DQ15927",
        "user": "AIRLINE_DEV",
        "role": "AIRLINE_DEV_ROLE",
        "database": "AIRLINE_DB",
        "warehouse": "AIRLINE_DEV_WH",
    }
    if (
        cloud_kind != "warehouse"
        or any(str(params.get(k, "")).upper() != v for k, v in expected.items())
        or any(
            params.get(k)
            for k in (
                "private_key",
                "private_key_file",
                "private_key_file_pwd",
                "password",
                "token",
            )
        )
    ):
        raise ValueError("dbt must use only the pinned warehouse task identity")
    return {
        **params,
        "authenticator": "SNOWFLAKE_JWT",
        "private_key": private_key("builder", cloud_kind, deadline=deadline),
    }


def private_key(kind, cloud_kind, *, deadline=None):
    """Return validated DER in memory; no key files, logs or automatic rotation."""
    import boto3
    from botocore.config import Config
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    if kind not in SECRETS or SECRETS[kind][0] != cloud_kind:
        raise ValueError("Task cannot select another workload identity")
    remaining = 5 if deadline is None else min(5, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Credential acquisition deadline exhausted")
    _, arn, version, user, role = SECRETS[kind]
    client = boto3.client(
        "secretsmanager",
        region_name="us-east-2",
        config=Config(
            connect_timeout=remaining, read_timeout=remaining, retries={"total_max_attempts": 1}
        ),
    )
    response = client.get_secret_value(SecretId=arn, VersionId=version)
    raw = response.get("SecretString", "")
    if (
        response.get("ARN") != arn
        or response.get("VersionId") != version
        or not 0 < len(raw) <= 16384
    ):
        raise ValueError("Wrong or unbounded workload credential version")
    value = json.loads(raw)
    expected = dict(
        contract="snowflake-keypair-v1", account="LMOOEWP-DQ15927", user=user, role=role
    )
    if (
        not isinstance(value, dict)
        or set(value) != set(expected) | {"private_key_pem"}
        or any(value[k] != v for k, v in expected.items())
    ):
        raise ValueError("Credential identity is not the approved workload")
    key = serialization.load_pem_private_key(value["private_key_pem"].encode(), password=None)
    if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("Workload requires its approved RSA key pair")
    return key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

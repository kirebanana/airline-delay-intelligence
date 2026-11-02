"""Finite secret-free task probe, not Snowflake authentication or a data refresh.

Pulling this image exercises the ECS execution role's ECR path. The job's own
role separately proves exact S3 read/conditional write and denied state access.
No credential retrieval, SQL, source acquisition, role assumption or recovery.
"""

import base64
import hashlib
import http.client
import json
import os
import re
import signal
import ssl
import time

BUCKET = "airline-bts-336805808138-us-east-2"
STATE_BUCKET = "airline-state-336805808138-us-east-2"
SNOWFLAKE_HOST = "lmooewp-dq15927.snowflakecomputing.com"
_PREFIXES = {"acquisition": "acquisition", "warehouse": "build", "publisher": "publication"}
_FIELDS = {"request_id", "kind", "deadline_epoch", "manifest_key", "manifest_sha256"}


def _validate(request, now):
    if not isinstance(request, dict) or set(request) != _FIELDS:
        raise ValueError("Exact secret-free probe request required")
    if (
        not isinstance(request["kind"], str)
        or request["kind"] not in _PREFIXES
        or not isinstance(request["request_id"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", request["request_id"])
        or type(request["deadline_epoch"]) is not int
        or not 0 < request["deadline_epoch"] - now() <= 120
        or not isinstance(request["manifest_key"], str)
        or not re.fullmatch(
            r"manifests/prepared/bts/202[3-5]-(0[1-9]|1[0-2])/[a-f0-9]{64}/[a-f0-9]{64}[.]json",
            request["manifest_key"],
        )
        or not isinstance(request["manifest_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", request["manifest_sha256"])
    ):
        raise ValueError("Invalid scope, deadline or selected manifest")


def tls_probe(host, timeout):
    connection = http.client.HTTPSConnection(
        host, timeout=timeout, context=ssl.create_default_context()
    )
    try:
        connection.request("HEAD", "/")
        response = connection.getresponse()
        # A root HTTP 404/403 is still successful certificate-verified TLS, not
        # evidence of account authentication or SQL/S3 result transfer access.
        return response.status
    finally:
        connection.close()


def sdk_factory(service, remaining):
    import boto3
    from botocore.config import Config

    return boto3.client(
        service,
        region_name="us-east-2",
        config=Config(
            connect_timeout=min(5, remaining),
            read_timeout=min(5, remaining),
            retries={"total_max_attempts": 1, "mode": "standard"},
        ),
    )


def run_probe(request, *, client_factory=sdk_factory, https_probe=tls_probe, now=time.time):
    from botocore.exceptions import ClientError

    _validate(request, now)

    def remaining():
        value = request["deadline_epoch"] - now()
        if value <= 0:
            raise TimeoutError("Probe absolute deadline exhausted")
        return min(5, value)

    caller = client_factory("sts", remaining()).get_caller_identity()
    role = "airline-job-" + request["kind"]
    if caller.get("Account") != "336805808138" or not caller.get("Arn", "").startswith(
        "arn:aws:sts::336805808138:assumed-role/" + role + "/"
    ):
        raise ValueError("Wrong task identity; no operator/admin fallback")
    response = client_factory("s3", remaining()).get_object(
        Bucket=BUCKET, Key=request["manifest_key"]
    )
    stream = response["Body"]
    try:
        body = stream.read(16385)
    finally:
        stream.close()
    if len(body) > 16384 or hashlib.sha256(body).hexdigest() != request["manifest_sha256"]:
        raise ValueError("Selected manifest bytes do not match approved probe input")
    try:
        client_factory("s3", remaining()).head_object(
            Bucket=STATE_BUCKET, Key="aws/ingestion.tfstate"
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in ("403", "AccessDenied"):
            raise ValueError("State denial was not established") from error
    else:
        raise ValueError("Unexpected Terraform-state access")
    status = https_probe(SNOWFLAKE_HOST, remaining())
    if type(status) is not int or not 100 <= status <= 599:
        raise ValueError("Snowflake TLS transport not established")
    result = {
        "status": "CONNECTIVITY_ONLY",
        "request_id": request["request_id"],
        "kind": request["kind"],
        "caller_arn": caller["Arn"],
        "manifest_sha256": request["manifest_sha256"],
        "state_access": "DENIED",
        "snowflake_https_status": status,
        "snowflake_authenticated": False,
        "completed_epoch": int(now()),
    }
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    client_factory("s3", remaining()).put_object(
        Bucket=BUCKET,
        Key=f"reports/{_PREFIXES[request['kind']]}/{request['request_id']}/connectivity.json",
        Body=payload,
        IfNoneMatch="*",
        ServerSideEncryption="AES256",
        ChecksumSHA256=base64.b64encode(hashlib.sha256(payload).digest()).decode(),
        ContentType="application/json",
    )
    return result


def main():
    def expired(signum, frame):
        raise TimeoutError("Probe process deadline exhausted")

    try:
        raw = os.environ.get("AIRLINE_PROBE_REQUEST", "")
        if not 0 < len(raw.encode()) <= 4096:
            raise ValueError("Bounded probe input required")
        request = json.loads(raw)
        _validate(request, time.time)
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request["deadline_epoch"] - time.time())
        result = run_probe(request)
    except Exception as error:
        # Never serialize SDK errors, tokens, HTTP responses or environment values.
        print(json.dumps({"status": "PROBE_FAILED", "error_type": type(error).__name__}))
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

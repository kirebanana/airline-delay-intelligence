"""Bounded read-only Snowflake authentication/result-transfer qualification.

No source load, candidate, claim, publication, role grant or recovery mutation.
Evidence explicitly separates authentication from chunk-transfer compatibility.
"""

import hashlib
import json
import logging
import os
import re
import signal
import time
from urllib.parse import urlsplit

from airline_warehouse.connection import connect_as
from airline_warehouse.connectivity_probe import BUCKET, sdk_factory
from airline_warehouse.load import check_account_monitor


def main():
    logging.disable(logging.CRITICAL)
    started = time.monotonic()
    result = {"status": "FAILED", "authenticated": False, "transfer": "NOT_RUN"}
    conn = None
    request = None

    def expired(signum, frame):
        raise TimeoutError("Authentication probe deadline exhausted")

    try:
        request = json.loads(os.environ["AIRLINE_AUTH_REQUEST"])
        if set(request) != {"request_id", "kind", "deadline_epoch", "transfer"}:
            raise ValueError("Exact authentication-probe request required")
        if (
            request["kind"] not in ("warehouse", "publisher")
            or request["kind"] != os.environ.get("AIRLINE_CLOUD_IDENTITY")
            or not re.fullmatch(r"[a-f0-9]{32}", request["request_id"])
            or type(request["transfer"]) is not bool
            or type(request["deadline_epoch"]) is not int
            or not 0 < request["deadline_epoch"] - time.time() <= 180
        ):
            raise ValueError("Wrong authentication-probe scope/deadline")
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request["deadline_epoch"] - time.time())
        deadline = time.monotonic() + request["deadline_epoch"] - time.time()
        result.update(request_id=request["request_id"], kind=request["kind"])
        kind = "builder" if request["kind"] == "warehouse" else "publisher"
        conn = connect_as(kind, deadline=deadline)
        result["authenticated"] = True
        with conn.cursor() as cur:
            cur.execute(
                "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=60, "
                "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=10, LOCK_TIMEOUT=5, "
                "QUERY_TAG='airline:auth:" + request["request_id"] + "'"
            )
            cur.execute("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
            names = [x[0].lower() for x in cur.description]
            monitors = [dict(zip(names, row, strict=True)) for row in cur.fetchall()]
            if len(monitors) != 1:
                raise ValueError("Expected account monitor")
            check_account_monitor(monitors[0])
            if float(monitors[0]["remaining_credits"]) <= 0.5:
                raise ValueError("Recovery reserve reached")
            result["monitor_used"] = str(monitors[0]["used_credits"])
            result["monitor_remaining"] = str(monitors[0]["remaining_credits"])
            if request["transfer"]:
                cur.execute(
                    "SELECT n, SHA2(n||'a',256)||SHA2(n||'b',256)||"
                    "SHA2(n||'c',256)||SHA2(n||'d',256) FROM "
                    "(SELECT SEQ4()::VARCHAR n FROM TABLE(GENERATOR(ROWCOUNT=>65536)))"
                )
                result["query_id"] = cur.sfqid
                count = 0
                digest = hashlib.sha256()
                while rows := cur.fetchmany(1000):
                    for n, payload in rows:
                        expected = "".join(
                            hashlib.sha256((n + c).encode()).hexdigest() for c in "abcd"
                        )
                        if payload.lower() != expected:
                            raise ValueError("Transferred result bytes did not reconcile")
                        digest.update((n + payload).encode())
                        count += 1
                if count != 65536:
                    raise ValueError("Incomplete transferred result")
                result.update(transfer="VERIFIED", rows=count, result_sha256=digest.hexdigest())
        result["status"] = "COMPLETED"
    except Exception as error:
        result["error_type"] = type(error).__name__
        # Keep only hostnames, never signed paths/queries/response bodies.
        result["error_hosts"] = sorted(
            {
                urlsplit(url).hostname
                for url in re.findall(r"https?://[^\s'\"<>]+", str(error))
                if urlsplit(url).hostname
            }
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                result["close_uncertain"] = True
        result["elapsed_seconds"] = time.monotonic() - started
        if request and result.get("request_id"):
            prefix = "build" if request["kind"] == "warehouse" else "publication"
            body = json.dumps(result, sort_keys=True).encode()
            try:
                sdk_factory("s3", 5).put_object(
                    Bucket=BUCKET,
                    Key=f"reports/{prefix}/{request['request_id']}/auth.json",
                    Body=body,
                    ContentType="application/json",
                    ServerSideEncryption="AES256",
                    IfNoneMatch="*",
                )
            except Exception:
                result["report_write_failed"] = True
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "COMPLETED" and not result.get("report_write_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

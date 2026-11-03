"""Create-only small S3 reports and durable pre-query evidence; no launch authority."""

import base64
import hashlib
import json
import re
import time
import uuid

from airline_warehouse.connectivity_probe import BUCKET
from airline_warehouse.execution import WorkJournal

PREFIXES = {"acquisition": "acquisition", "warehouse": "build", "publisher": "publication"}
LIMIT = 16384


class ReportStore:
    def __init__(self, client, kind, request_id):
        if kind not in PREFIXES or not re.fullmatch(r"[a-f0-9]{32}", request_id):
            raise ValueError("Exact workload/request scope required")
        self.client, self.kind, self.request_id = client, kind, request_id
        self.prefix = f"reports/{PREFIXES[kind]}/{request_id}/"

    def write(self, name, value):
        return self._write(name, value, LIMIT)

    def write_payload(self, name, value):
        if name not in ("candidate-payload.json", "descriptor-payload.json"):
            raise ValueError("Only bounded candidate/release payloads live outside control state")
        return self._write(name, value, 65536)

    def _write(self, name, value, limit):
        if not re.fullmatch(r"[A-Za-z0-9_-]+[.]json", name):
            raise ValueError("One request-scoped report name required")
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if not 0 < len(body) <= limit:
            raise ValueError("Small control report exceeds its bound")
        digest = hashlib.sha256(body).digest()
        key = self.prefix + name
        self.client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
            ServerSideEncryption="AES256",
            ChecksumSHA256=base64.b64encode(digest).decode(),
        )
        return {"key": key, "sha256": digest.hex()}

    def read(self, reference):
        return self._read(reference, LIMIT)

    def read_payload(self, reference):
        if not isinstance(reference, dict) or reference.get("key", "").rsplit("/", 1)[-1] not in (
            "candidate-payload.json",
            "descriptor-payload.json",
        ):
            raise ValueError("Unknown large dependency payload")
        return self._read(reference, 65536)

    def _read(self, reference, limit):
        if not isinstance(reference, dict) or set(reference) != {"key", "sha256"}:
            raise ValueError("Exact immutable report reference required")
        key, digest = reference["key"], reference["sha256"]
        # Stage dependencies may read another role's permitted reports, but never
        # another request, arbitrary source/state keys or caller-selected buckets.
        if (
            not isinstance(key, str)
            or not re.fullmatch(
                rf"reports/(acquisition|build|publication)/{self.request_id}/[A-Za-z0-9_-]+[.]json",
                key,
            )
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("Reference escapes the approved request reports")
        stream = self.client.get_object(Bucket=BUCKET, Key=key)["Body"]
        try:
            body = stream.read(limit + 1)
        finally:
            stream.close()
        if len(body) > limit or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("Report bytes do not match the immutable dependency")
        return json.loads(body)

    def journal(self, path, *, deadline=None):
        return CloudJournal(path, self, deadline=deadline)


class CloudJournal(WorkJournal):
    def __init__(self, path, store, *, deadline=None):
        super().__init__(path)
        self.store = store
        self.deadline = deadline

    def execute(self, execute, cursor, session_id, sql, *args, **kwargs):
        def wire(command, *a, **kw):
            if self.deadline is not None:
                remaining = int(self.deadline - time.monotonic())
                if command.strip().upper() == "ROLLBACK":
                    remaining = max(remaining, 5)
                elif remaining < 1:
                    raise TimeoutError("SQL deadline exhausted while persisting query intent")
                remaining = min(600, remaining)
                command = re.sub(
                    r"\b(STATEMENT_TIMEOUT_IN_SECONDS|STATEMENT_QUEUED_TIMEOUT_IN_SECONDS|"
                    r"LOCK_TIMEOUT)\s*=\s*(\d+)",
                    lambda m: f"{m[1]}={min(int(m[2]) or remaining, remaining)}",
                    command,
                    flags=re.I,
                )
                kw["timeout"] = min(kw.get("timeout") or remaining, remaining)
                params = dict(kw.get("_statement_params") or {})
                for name, limit in (
                    ("STATEMENT_TIMEOUT_IN_SECONDS", remaining),
                    ("STATEMENT_QUEUED_TIMEOUT_IN_SECONDS", min(60, remaining)),
                    ("LOCK_TIMEOUT", min(5, remaining)),
                ):
                    params[name] = min(int(params.get(name, limit)) or limit, limit)
                kw["_statement_params"] = params
            return execute(command, *a, **kw)

        return super().execute(wire, cursor, session_id, sql, *args, **kwargs)

    def append(self, event, **fields):
        # Confirm remote durability BEFORE returning to a data-capable caller.
        # A lost PUT acknowledgement blocks the SQL submission, never retries it.
        self.store.write(
            "event-" + uuid.uuid4().hex + ".json", {"event": event, "at": time.time(), **fields}
        )
        super().append(event, **fields)

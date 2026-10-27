# January BTS preparation and raw ingestion

Implementation runbook, 2026-10-27. Scope: authorized tickets 01–04 against approved
specification baseline `b01f2ad499bc3d4b996f6cc0b9fa2df735aa2abd` and the owner's
revised data-first order. This is not an amendment to final product requirements.
**Live ingestion is blocked; the code is not yet Snowflake-qualified.**

## Local preparation (no cloud access)

Python 3.12; runtime preparation uses only the standard library. From this repository:

```bash
uv sync --locked
uv run airline prepare --archive /private/path/marketing-2025-01.zip \
  --month 2025-01 \
  --expected-sha256 0feaabdbc9e4bd851ef717f342678cdcc5ea0822dd706359aab030bb1a5d1c24 \
  --output /private/path/new-artifact-directory
uv run airline plan-load --artifact /private/path/new-artifact-directory \
  --bucket airline-bts-336805808138-us-east-2
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
```

The official archive is an explicit local import from BTS's marketing-carrier table,
not a new download. Preserve it unchanged; SHA-256 pins bytes, not BTS authenticity.
Synthetic fixtures must be labelled `--synthetic`; their load tables use INGEST_TEST.
`prepared.csv.gz` retains all 119 source values, including signed delays, unknowns,
sentinels, leading zeros and empty strings, plus ZIP hash, one-based source-row
ordinal and a length-delimited UTF-8 SHA-256 row fingerprint. Only the documented
Operating_Airline header space/trailing empty column are normalized. No business-key
deduplication, timezone interpretation or eligibility filtering occurs here.

Manifest v1 records source/preparation/artifact identities, schema, counts, bytes,
source URL and ZIP member. Gzip has no filename/timestamp. Exact compressed identity
should be reproduced with the same Python/zlib environment; changes across toolchains
produce a new identity rather than overwrite the old artifact.

Limits: ZIP 100 MiB, declared expanded size 1 GiB, compressed output 200 MiB,
1 million rows, default 300-second cooperative preparation timeout (maximum 600).
CSV parsing has the standard-library field-size limit. CRCs are checked while reading
the CSV/readme to EOF; no filesystem extraction occurs. Work is streamed; output
completion is indicated by manifest written last. Existing destinations are refused;
after interruption, inspect and retain/quarantine incomplete outputs rather than
automatically retrying over them. Hard process/disk quotas are not implemented.

## Cloud hold points and setup order

Target AWS account `336805808138`, profile `airline-old-dev`, Ohio `us-east-2`;
Snowflake connection `airline`, account locator `DC50202`, role AIRLINE_DEV_ROLE,
database AIRLINE_DB and warehouse AIRLINE_DEV_WH. No alternate/admin workload identity.

1. Owner verifies **actual current** AWS credits, eligible S3/request/transfer services,
   expiration and shared usage in Billing; and Snowflake trial balance/expiry in
   ACCOUNTADMIN's Snowsight trial tile. Free Tier plan status is not a credit balance.
   Neither credit is a hard $0 cap. Do not upgrade billing or enable paid services.
2. An already authorized human administrator reviews/applies
   `sql/01_warehouse_safeguards.sql`: project-only non-resetting 5-credit monitor,
   notify at 50%, suspend at 75%, immediate suspend at 90%, disable Query Acceleration,
   X-Small, auto-suspend 60s, statement 600s and queue 60s. Inspect existing monitor
   settings if it already exists; IF NOT EXISTS does not repair drift. No workload-role
   elevation. Resource monitors can overshoot and do not cover storage/serverless.
3. Review `infra/ingestion/` using Terraform 1.13.4 and locked AWS provider 6.33.0:
   `terraform init`, `terraform validate`, `terraform test`, then a separately reviewed
   live plan only after the funding hold point. Mock tests make **no AWS calls**.
   `funding_verified` defaults false. Never use `-target` to bypass this guard.
   Initial trust explicitly denies AssumeRole. This creates only one private bucket,
   public-access/ACL/ownership controls, SSE-S3, TLS-only policy and a new prepared-only
   read role/policy; it does not modify airline-project-dev. No KMS, versions, compute,
   recurring jobs, remote-state bucket or deployment workflow.
4. An authorized integration administrator applies `sql/03_storage_integration.sql`
   after the closed-trust role exists. Capture its exact generated IAM user ARN and
   external ID privately. Set both Terraform inputs together, inspect the trust diff,
   then apply only the new role's exact principal/external-ID trust. No account-root
   wildcard allow. Service role receives integration USAGE, not CREATE INTEGRATION.
5. Apply `sql/04_external_stage.sql` as the service identity; inspect actual stage URL,
   integration and file-format properties (IF NOT EXISTS does not correct drift).
   Upload only selected source ZIP, prepared gzip and manifest under `object_keys()`'s
   content-addressed paths, using conditional create/checksum checks; existing different
   content is a hard failure. No automated uploader is implemented in this blocked slice.
   Read back/check SHA-256, including via the stage; validate permitted prefix access
   and denied outside-prefix access before COPY. Never upload a ZIP as CSV.

Local Terraform state/plan/tfvars files remain ignored; protect the directory with
owner-only permissions and an encrypted owner-controlled backup. Do not put credentials
in inputs or state. Bucket prevent_destroy/force_destroy=false are deliberate: no
automatic data deletion or cloud rollback. Attended cleanup requires owner-approved
object/resource inventory and cost verification, including storage beyond credit expiry.

## First COPY (not executed)

Only after all hold points and object checks pass:

```bash
uv sync --locked --extra load
uv run airline load --artifact /private/path/new-artifact-directory \
  --bucket airline-bts-336805808138-us-east-2 --funding-verified
```

The optional pinned connector reuses the existing named key-pair connection; no key
copying. A required passphrase comes from local `AIRLINE_KEY_PASSPHRASE`, never Git.
The funding flag is an operator attestation, not a live billing API verification.
The loader checks warehouse size, positive bounded auto-suspend, disabled acceleration
and named monitor before workloads, and sets bounded session query/queue/lock timeouts.
Operator inspection must verify monitor thresholds and stage/file-format drift.

One transient, zero-retention raw table per artifact, 122 NOT NULL columns (only ordinal
numeric). Strict CSV preserves empty strings; COPY uses ABORT_STATEMENT, FORCE=false,
PURGE=false. Acceptance checks full-row fingerprints, row/ordinal/source/month and
DEN outcome counts before COMMIT. Existing complete data is revalidated/reused,
not trusted solely because COPY history exists; partial tables are rejected.
DDL is outside the transaction and may leave an empty table after failure.

Run **one attended loader at a time**. No concurrency claim, automatic recovery,
publication transaction or periodic watchdog exists in this slice. On timeout/client
failure or unknown COMMIT, retain query IDs, inspect the exact table and query history,
and independently reconcile before another attempt; never blindly retry, truncate,
FORCE-load or repoint a published artifact. Live tests still required: exact SQL syntax,
external access/denials, malformed COPY rollback, full/repeat load, lost-ack recovery
and concurrent writers. Mock connector tests prove only client control flow.

## Verified local January evidence

Two full preparations have identical manifests/gzip hashes. An independent streaming
comparison checked every source value and all lineage across **599,013 rows × 119
source fields**, with no differences. DEN: **24,732**, including **313 cancellations**
and **69 diversions**. National cancellations **18,740**, diversions **1,316**.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Source ZIP | 31,599,374 | `0feaabdbc9e4bd851ef717f342678cdcc5ea0822dd706359aab030bb1a5d1c24` |
| Prepared gzip | 58,297,889 | `e16a0b63d28801cc023ab668c61cdb7c357f4e2cc8b6f48d8c24727035bd187a` |

Payload hash: `d157cd8265af901ab310aae74497a1c294c07183802b42469eb86581f6d588b9`.
Loaded artifact ID: `eb0c52473e89616864f5287d54d2110eb0f53036ecd977e31b7f15671581d7c2`.
**Snowflake rows loaded by this batch: 0.** No real SQL/data-plane result is inferred
from local source counts or mocks.

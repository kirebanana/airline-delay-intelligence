# January BTS preparation and raw ingestion

Implementation runbook, 2026-10-27. Scope: authorized tickets 01–04 against approved
specification baseline `b01f2ad499bc3d4b996f6cc0b9fa2df735aa2abd` and the owner's
revised data-first order. This is not an amendment to final product requirements.
**Live ingestion is blocked; the code is not yet Snowflake-qualified.**

Latest deployment verification (2026-10-27): X-Small, suspended, auto-suspend60,
acceleration=false, statement timeout600 and queue timeout60. AIRLINE_BUDGET is now
visible: ACCOUNT level, MONTHLY, quota5, used0, notify50%, immediate suspend100%, no
graceful-suspend trigger. It was not modified or attached to the warehouse. The loader
preflight passes against the actual monitor output.

Owner confirms AWS promotional credit156.20USD remaining/3.80used, expiryJuly2027,
and Snowflake400USD/30-day trial. These are owner attestations, not agent billing API
results. Exact credit Applicable Products/tax/shared usage remain unobservable through
the AWS role; see cost caveats below. Seven Terraform resources are deployed and a
post-deployment plan shows no drift. Source/prepared/manifest objects are uploaded and
S3 full-object SHA-256 verified. Strict BTS_CSV_V1 exists; integration creation still
fails003001/42501 (missing CREATE INTEGRATION on ACCOUNT). **No stage or raw rows yet.**
Sixteen Python tests, lint/format and three Terraform mock tests pass; real replay,
failure handling and COPY remain untested on Snowflake.

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
   Balance/expiry and trial entitlement are owner-confirmed above; public AWS terms
   do not generally exclude standard S3, but credit-specific service restrictions and
   taxes cannot be inferred from a balance. IAM has no additional charge; no KMS or
   other metered supporting service is provisioned. Neither credit is a hard $0 cap.
   Do not upgrade billing or enable additional paid services.
2. Run read-only `sql/01_warehouse_safeguards.sql`. Keep the existing account-level
   AIRLINE_BUDGET unchanged; a null warehouse resource_monitor is expected. For missing
   monitor visibility, the human owner runs `sql/00_owner_verification.sql` using
   ACCOUNTADMIN: SHOW confirms its ACCOUNT level, actual quota, used credits and suspend/
   immediate-suspend triggers. The owner has now granted MONITOR-only visibility;
   the agent never executes grants to broaden access. No assumed suspension threshold
   is substituted for the actual100% immediate trigger. Resource monitors can
   overshoot and do not cover storage/serverless; owner checks notifications separately.
3. Review `infra/ingestion/` using Terraform 1.13.4 and locked AWS provider 6.33.0:
   `terraform init`, `terraform validate`, `terraform test`, then a separately reviewed
   live plan with the funding guard left false until evidence exists. Mock tests make
   **no AWS calls**. Following owner funding confirmation and deployment authorization,
   a saved plan for7 additions/0changes/0deletions was reviewed and applied; the final
   live plan reports no changes. State is local/ignored with owner-only file permissions.
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
   This is the exact owner-run SQL for the observed privilege blocker; use the owner's
   existing ACCOUNTADMIN session, not the service identity. Do not grant CREATE
   INTEGRATION or ACCOUNTADMIN to the workload role. Do not run it until funding and
   the closed-trust role bootstrap have passed.
5. Apply `sql/04_external_stage.sql` as the service identity; inspect actual stage URL,
   integration and file-format properties (IF NOT EXISTS does not correct drift).
   Upload only selected source ZIP, prepared gzip and manifest under `object_keys()`'s
   content-addressed paths, using conditional create/checksum checks; existing different
   content is a hard failure. All three objects were uploaded using short-lived signed
   PUTs with If-None-Match=* and ChecksumSHA256; HeadObject independently verified
   FULL_OBJECT checksums/lengths/AES256. Signed URLs were not logged. Transfer workers
   were bounded, loopback-only and closed after completion; no recurring uploader exists.
   A bounded repeat conditional PUT to the existing manifest returned PreconditionFailed;
   a subsequent HeadObject confirmed the original manifest checksum/length unchanged.
   This proves the S3 no-overwrite boundary, not Snowflake COPY idempotency.
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
The loader checks warehouse size, positive bounded auto-suspend and disabled acceleration,
then inspects the existing account-level AIRLINE_BUDGET before workloads. It refuses
an invisible/wrong-level monitor, nonpositive/nonfinite quota, missing immediate
suspension, triggers above100%, or a used-credit balance at/above the first suspension
threshold. A null graceful-suspend trigger is valid when immediate suspension exists.
It sets bounded session query/queue/lock timeouts. It never creates/changes a monitor.
Funding/lifecycle coverage and stage/file-format drift still require operator inspection.

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

## Deployed bootstrap and cost evidence

Bucket: `airline-bts-336805808138-us-east-2`. Role:
`arn:aws:iam::336805808138:role/airline-snowflake-bts-read`, inline policy
`airline-read-prepared-only`. Public access blocked in all four settings; ownership
BucketOwnerEnforced; SSE-S3 AES256; SSE-C blocked; TLS-only bucket policy; no versioning.
Role reads/list only prepared/, with no upload/delete permissions; trust is currently
explicit DENY ALL, not a broad placeholder allow. Integration-generated principal and
external ID are still unavailable; do not invent or enable trust before owner bootstrap.

Stored source31,599,374 + prepared58,297,889 + manifest6,890 =89,904,153bytes.
At the public Ohio S3 Standard first-tier0.023USD/GB-month, storage is approximately
0.002USD/month before credits, plus small request charges. This is an estimate, not a
measured bill or $0 guarantee. No paid warehouse workload has run; monitor reports
0.00credits used. Retention beyond credits/trial expiry and shared usage remain risks;
review cleanup before expiry, without automatic deletion of retained evidence.

Public sources checked2026-10-27: [credit terms](https://aws.amazon.com/awscredits/)
(credit-specific Eligible Services and tax exclusions),
[credit applicability](https://repost.aws/knowledge-center/aws-promotional-credit),
and [Ohio S3 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-2/index.json)
(published2026-10-15). Applicable Products in the owner's credit console remains the
authority for that specific credit; the restricted service role cannot confirm it.

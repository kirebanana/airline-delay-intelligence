# January BTS preparation and raw ingestion

Implementation runbook, 2026-10-27. Scope: authorized tickets 01–04 against approved
specification baseline `b01f2ad499bc3d4b996f6cc0b9fa2df735aa2abd` and the owner's
revised data-first order. This is not an amendment to final product requirements.
**Tickets 01–04: end-to-end January ingestion verified; ready for batch review.**

Latest deployment verification (2026-10-27): X-Small, suspended, auto-suspend60,
acceleration=false, statement timeout600 and queue timeout60. AIRLINE_BUDGET is now
visible: ACCOUNT level, MONTHLY, quota5, initial used0, notify50%, immediate suspend100%, no
graceful-suspend trigger. It was not modified or attached to the warehouse. The loader
preflight passes against the actual monitor output.

Owner confirms AWS promotional credit156.20USD remaining/3.80used, expiryJuly2027,
and Snowflake400USD/30-day trial. These are owner attestations, not agent billing API
results. Exact credit Applicable Products/tax/shared usage remain unobservable through
the AWS role; see cost caveats below. Seven Terraform resources are deployed and a
post-deployment plan shows no drift. Source/prepared/manifest objects are uploaded and
S3 full-object SHA-256 verified. The human owner created AIRLINE_BTS_S3 and granted
integration USAGE. Terraform then applied one reviewed in-place update binding the
new role to the exact Snowflake-generated IAM user and external ID; no broad trust.
The service role created BTS_EXTERNAL_STAGE. Actual raw rows: **599,013**, including
**24,732 DEN**. Repeat execution reuses the verified artifact without COPY or duplicates.
Sixteen offline tests, four opt-in live tests and three Terraform mock tests pass,
as do lint/format/validation. Final live Terraform plan reports no drift. Ticket05
and publication/model/dashboard work were not started.

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
   the closed-trust role bootstrap have passed. This bootstrap is now complete:
   exact generated values are stored only in ignored, owner-only
   `infra/ingestion/bootstrap.auto.tfvars` and protected Terraform state/plan files.
   Existing integration ownership remains ACCOUNTADMIN; stage/file format/raw tables
   are AIRLINE_DEV_ROLE-owned. Do not recreate the integration: that changes trust IDs.
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
Run Terraform with `umask 077`; formatters can rewrite local input files, so recheck
state/tfvars file modes0600 afterward. Mock tests explicitly override operator funding/
trust inputs and never inherit live bootstrap values as their test scenario.

## First COPY and subsequent reuse

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

Run **one bounded loader at a time**. No concurrency claim, automatic recovery,
publication transaction or periodic watchdog exists in this slice. On timeout/client
failure or unknown COMMIT, retain query IDs, inspect the exact table and query history,
and independently reconcile before another attempt; never blindly retry, truncate,
FORCE-load or repoint a published artifact. Real SQL, stage access/denial, malformed
COPY rejection/rollback, wrong-partition rollback, wrong-format rejection and replay
are now tested. Lost-ack recovery is mocked only; concurrent writers are unqualified.
Those are not claims of this single-writer initial-ingestion batch. No result is
published and no refresh/correction workflow is implemented here.

### Opt-in live regression tests

Default unittest discovery skips live tests. They require a separately prepared/staged,
explicitly synthetic artifact of at most10rows, never the official raw table:

```bash
AIRLINE_LIVE_TESTS=funded-01-04 \
AIRLINE_TEST_ARTIFACT=/private/path/to/synthetic-artifact \
  uv run python -m unittest discover -s tests -p test_live_ingestion.py -v
```

Prepare synthetic inputs with the same `prepare(..., synthetic=True)` interface and
the small hand-authored `archive()` helper in tests/test_prepare.py. Stage its gzip at
`object_keys(manifest)['prepared']`. The executed fixture has two rows, Unicode,
embedded comma/quote/newline, signed delay and cancellation with a recorded departure.
Additionally stage gzip CSVs at `prepared/tests/01-04/<artifact-id>/malformed.csv.gz`
and `wrong-month.csv.gz`: keep the full prepared header; make the last row one field
short in malformed; change every FlightDate to2025-02-01 in wrong-month without updating
lineage hashes. Use conditional checksum-verified uploads, not overwrites. The suite
checks fixture load/reuse, malformed+valid multi-file COPY, wrong partition/fingerprint
acceptance and deliberately wrong compression. Failure tables are TEMPORARY in
INGEST_TEST, verified empty after ROLLBACK, and disappear when the session closes.
The accepted two-row fixture table remains isolated from RAW. Do not run this command
without current funding and explicit bounded workload authorization.

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
**Snowflake rows loaded:599,013** in
`AIRLINE_DB.RAW.BTS_202501_EB0C52473E89616864F5287D54D2110E` (transient, retention0).
Exact122columns/order/types verified. Distinct ordinals599,013, min1/max599,013;
wrong source0, wrong month0, full119-field fingerprint mismatches0. DEN cancellations
313/diversions69. Independent queries against original ZIP-derived aggregate expectations
also matched31dates (January1–31), national cancellations18,740/diversions1,316,
negative arrival delays378,711, empty arrival delays20,056, delay14/15 counts3,829/3,614,
cancelled-with-departure479, leading-zero scheduled clocks176,513 and differing
marketer/operator codes195,119. No duplicates or imputation were introduced.

COPY query `01c8042c-0309-57a4-0012-6aee00015d26`: SUCCESS,599,013 inserted,
58,297,889bytes scanned,10.117seconds. Acceptance query
`01c8042c-0309-57a4-0012-6aee00015d2a`; full-table reuse validation
`01c8042d-0309-5de7-0012-6aee000170ca` returned reused without a second COPY.
Independent aggregate/schema query `01c8042f-0309-5de7-0012-6aee000170ce` matched
all source-derived expectations. A final persisted COUNT remained599,013 after tests.

## Deployed bootstrap and cost evidence

Bucket: `airline-bts-336805808138-us-east-2`. Role:
`arn:aws:iam::336805808138:role/airline-snowflake-bts-read`, inline policy
`airline-read-prepared-only`. Public access blocked in all four settings; ownership
BucketOwnerEnforced; SSE-S3 AES256; SSE-C blocked; TLS-only bucket policy; no versioning.
Role reads/list only prepared/, with no upload/delete permissions; trust allows only
the exact generated Snowflake IAM user with exact external ID. AWS GetRole independently
verified both. Allowed-stage LIST succeeded; attempted stage creation at original/
was rejected003127/42601 by the integration's allowed-location restriction. This is
live Snowflake boundary evidence plus IAM policy inspection, not a claim that the
service role can impersonate Snowflake to test arbitrary AWS APIs directly.

Stored source31,599,374 + prepared58,297,889 + manifest6,890 =89,904,153bytes,
plus three tiny synthetic gzip fixtures (2,650bytes), total six objects/89,906,803bytes.
At the public Ohio S3 Standard first-tier0.023USD/GB-month, storage is approximately
0.002USD/month before credits, plus small request charges. This is an estimate, not a
measured bill or $0 guarantee. The main COPY ran10.117seconds; actual warehouse credit
metering/billing details are not visible through this restricted role. A bounded
own-query-history capture reported0.00309cloud-services credits across91tagged queries;
this is **not total compute/billed credits** and daily billing adjustments/latency apply.
No new billing privileges, paid usage tools or warehouse polling were enabled. Raw and
fixture Snowflake storage also incur trial-covered usage. Retention beyond credits/
trial expiry and shared usage remain risks; review cleanup before expiry without
automatic deletion of retained evidence.

Final metadata: warehouse **SUSPENDED**, no running/queued queries; account monitor
reports **0.12credits used/4.88remaining** (initial0.00, account-wide/rounded/lagged,
not a final invoice or exclusive per-query attribution). RAW table storage54,129,664
bytes; accepted synthetic table5,120bytes. Only these two persistent data tables
remain; failure-test temporary tables closed with their sessions.

Public sources checked2026-10-27: [credit terms](https://aws.amazon.com/awscredits/)
(credit-specific Eligible Services and tax exclusions),
[credit applicability](https://repost.aws/knowledge-center/aws-promotional-credit),
and [Ohio S3 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-2/index.json)
(published2026-10-15). Applicable Products in the owner's credit console remains the
authority for that specific credit; the restricted service role cannot confirm it.

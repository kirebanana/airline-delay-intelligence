# Finite cloud jobs: qualification status

**Status: partial implementation and live tracer qualified, 2026-11-03.**
This is implementation evidence, not final acceptance of tickets 16–20 or a new
authorization to run data work. See the [approved specification](specifications/airline-delay-intelligence.md)
and [platform adoption history](terraform-adoption.md).

## Implemented boundary

`cloud_stage.py` adapts the existing loader, dbt candidate builder and publication
protocol. Only isolated `test_<hex>` targets and one data-capable attempt are
admitted. The original request format selects one accepted immutable month; the
version-2 request format references a checksum-bound selection of 1–36 unique
months and the compatible fixed weather dependency. Acquisition verifies existing
S3 inputs; it does **not** acquire a fresh archive. A complete baseline without
weather is refused. Large candidate/release payloads stay outside control state.

`cloud_workflow.py` generates a Standard Step Functions graph with four finite
`.sync` tasks: publisher admission, acquisition, warehouse/dbt/validation, publisher.
Success requires essential-container exit zero, exact deployment/request binding,
and hash-verified S3 reports. Unknown outcomes fail closed to attended recovery;
there is no automatic takeover, cleanup or data retry. Only side-effect-free S3
bridge reads retry once for named transient service errors. Exact-input replay
can finish after publisher admission without another warehouse build.

`infra/jobs/` owns only immutable task revisions and the versioned workflow. Its
`aws/jobs.tfstate` is separate from platform `aws/ingestion.tfstate`. Deployment
does not start a task or execution. No service, schedule, listener or new endpoint
was introduced. Task roles, secrets and platform networking remain platform-owned.

## Qualified immutable revision

- Image: `sha256:4454c579748da5aea7f99fca3ab84847cc66ec4bdb74c288c4a25422c61928da`.
- Processing contract: `ec5e0e0f579369a859876810840d0d368a895ee11199e53f35477631350340f6`.
- Workflow: `airline-isolated-refresh:1` in account `336805808138`, `us-east-2`.
- Execution: `tracer-50c2b36fcaa948f0a101cd0000000001`.
- Test target: `test_50c2b36fcaa948f0`; January 2023, **573,877 rows**.
- All four tasks stopped with exit zero. All 200 journalled queries were terminal;
  414 durable journal events were retained. The target claim was retired.
- Independent original-archive reconciliation passed source counts, signed delay
  quantiles, category populations/minutes, cancellation reasons, recovery measures,
  carrier/month/weekday/hour/origin populations and ordered DEN-route populations.
- Weather was explicitly absent; the partial release cannot inherit another
  release's weather qualification.
- The original 36-month, 22,562,477-row production release
  `02d263d7f7174890b6da97c15a81d098` was unchanged.

Measured maximum workflow state was 19,259 bytes against the 65,536-byte project
bound; ECS overrides were 5,018 bytes against the 8,192-byte service bound.
Referenced stage reports are additionally bounded to 10,000 bytes for workflow
hashing. Individual control reports remain at most 16 KiB.

The tracer added 75.937494403 seconds to the existing cumulative workload ledger;
the ledger was not reset. A subsequent read-only oracle assertion was reconciled
against both originating identities' complete session histories before another
operation was admitted. All 30 session statements succeeded; none began a
transaction or mutated data. Diagnostic and rerun time remain cumulative, and the
0.5-credit recovery reserve is unchanged. Monitor figures are rounded, lagged,
account-wide observations—not a bill or guaranteed spending cap.

## Security and remaining qualification

The deployed image passed 103 discovered offline/container tests with 31 live
skips. Basic ECR scanning reported **3 HIGH, 9 MEDIUM and 3 LOW** findings, including
`CVE-2026-5435`, `CVE-2026-85091` and `CVE-2026-19499`; it is not a clean scan.
No verified vulnerability remediation is claimed.

Newer source recomputes SQL client/server limits after durable query-intent I/O,
including dbt connections. Tests cover expiry before submission, decreasing limits
and bounded rollback cleanup. These changes are **not** in the qualified image
above; its separately tested promotion is recorded below. No data run using the
hardened revision has yet been qualified.

The hardened image
`sha256:044970830be50fb88346d3bf4624072f9d59b1e5024be2c663eef0a6f00a5cab`
was subsequently built, passed 106 discovered container tests with 31 live skips,
and was pushed once and independently digest-verified. Its saved promotion plan
was checked for three task-revision replacements retaining the original revisions
via `skip_destroy`, plus one workflow update. No other platform resource changes
are included. Basic scanning completed with the same 3 HIGH / 9 MEDIUM / 3 LOW
findings. Saved plan SHA256
`30b83311f8f6a7706a2fe9400e2e15ece88e971a2a361d4c72175dc5a1e4cfe1`
was hash-checked and applied: three new task revisions and one workflow update.
Terraform reports three logical removals from state, but `skip_destroy` retained
the old task definitions: independent AWS reads confirmed **both revisions 1 and
2 ACTIVE** for all three families. Workflow versions 1 and 2 also remain ACTIVE.
The version-2 graph differs only in exact image/task bindings. Independent reads
confirmed no running tasks or refreshes; promotion did not launch data work.

Runtime-contract preflight subsequently found that version 2 retained the old
processing hash despite the hardened dbt driver. No data run used that revision;
the mismatch would refuse admission before SQL. Do **not** choose version 2 for
rollback. Retain qualified version 1 instead. Subsequent image promotion now
records the processing hash measured inside the exact built image.

### Complete-module qualification in progress

Image `sha256:e6356147a0ad28b3dd64d192664967224dda9b77491ccd1e757da73d7c373c6b`
passed 112 discovered offline/container tests with 31 live skips. Its measured
processing contract is
`e97fb85ef90025b8eaee8d18d78e227d82511df0f276b5c4b26238204ef7d7ac`.
Basic scanning completed with the same known 3 HIGH / 9 MEDIUM / 3 LOW findings.
Reviewed saved plan
`0e290f9b340328579fa6ffcd235eb0451cb97dcc66dd8b065c35e928a594c90a`
registered task revisions 3 and workflow version 3, retaining old revisions.
It introduced selection references, the replay branch and bounded read retries,
not new IAM/network/secret resources or data starts on deployment.

The explicit isolated execution
`complete-baseline-9cef537a113f49edbe555fcff1f498dd` selects all 36 accepted months
and fixed DEN weather. Its terminal result and independent reconciliation are
still pending at this documentation checkpoint; deployment is not live acceptance.

Post-oracle plans for both AWS roots were clean. Independent AWS reads found no
running tasks, ECS services or refresh executions. Latest Snowflake metadata showed
zero running/queued statements, monitor quota 10.00, used 4.92 and remaining 5.08
credits. These remain account-wide observations, not final billing.

Still outstanding: complete module/weather cloud coverage, bounded transient
handling and launch/replay qualification; GitHub-executed CI and protected OIDC
promotion/rollback; real cloud abort/orphan/post-commit recovery tests; deferred
Snowflake infrastructure identity/adoption and remote state; final acceptance and
presentation packaging. The credential-free validation workflow contains no cloud
authentication, image push, deployment or data-start step.

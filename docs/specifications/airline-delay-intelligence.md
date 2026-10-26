# Airline Delay Intelligence — Technical Specification

| Field | Value |
| --- | --- |
| Status | **Approved architecture and implementation order; execution remains gated** |
| Version / date | 0.4 / 2026-10-26 |
| Approval date / owner | 2026-10-26 / project owner |
| Approved revision | Version 0.4; ticket drafts pin the Git commit containing this approved document |
| Product authority | [PRD v1.0, approved 2026-10-26](https://github.com/kirebanana/airline-delay-intelligence/blob/422c5c6baf2efbecb6f3bde4b87bbc77dcd44d68/docs/prds/airline-delay-intelligence.md) |
| PRD revision | `422c5c6baf2efbecb6f3bde4b87bbc77dcd44d68` |
| Architecture direction | R01 approved subject to real tests; R02 transient preferred; R03/R04 simplified per owner; R05 AWS qualification later; R06 population resolved from official semantics and complete boundary census |
| Testing seam | Approved refresh → validated release; focused tests plus independent infrastructure/security/delivery/cost evidence |
| Next gate | Review detailed ticket drafts, publication and implementation batches; separately authorize external effects |

The owner approved this architecture and implementation order on 2026-10-26 and
authorized specification promotion and detailed local ticket drafting. This
revision supersedes v0.3; the approved PRD is unchanged. Specification approval
does not authorize ticket publication, implementation, tool installation, account
configuration, cloud provisioning or Snowflake activation. Feasibility gates remain
mandatory and apply only to the phases they genuinely constrain.

## Problem Statement

The owner needs an explainable infrastructure-focused university/portfolio project
that produces trustworthy historical analytics without unnecessary production-grade
control machinery. AWS identity/funding uncertainty must not delay useful local
Python/dbt work, early real Snowflake integration, or a first official BTS month.
Conversely, early local execution must not become a substitute for the final
Terraform, S3, ECS/Fargate, Step Functions and GitHub Actions deliverables.

Required data remains BTS marketing-carrier coverage for 2023–2025 plus the bounded
Denver January-2025 ISD pilot. All six analytical areas, explicit eligibility and
provenance, atomic complete-release publication, independently checked results,
security evidence and **$0 out of pocket** remain required. The owner reviews
batches and learns the system; agent implementation does not require owner coding
or manual failure exercises.

## Solution

Build one refresh interface with local and later AWS execution adapters. Begin
with local acquisition/parsing and fixtures, then authorized real Snowflake/dbt
execution through a named internal stage. Prove lock-first publication and a first
official month before adding AWS storage/execution and deployment automation.

The completed path is official source → private S3 → Snowflake → dbt Core → an
immutable validated release → local Streamlit. Terraform adopts/manages the agreed
infrastructure; finite ECS jobs and ordinary Step Functions Standard coordination
run the same workload. GitHub Actions promotes reviewed code independently of data
execution. There is **no periodic watchdog, safety Lambda, autonomous reconciler,
cross-system deployment lock, or automatic stale-lease takeover in the baseline**.
Bounded clients/processes/server SQL, normal Retry/Catch handling, safe publication
and explicit recovery for uncertain work provide the proportional reliability model.

## User Stories

1. As a project owner, I want local progress independent of AWS qualification, so that account restrictions do not delay warehouse learning.
2. As a project owner, I want early real Snowflake results, so that fixtures do not conceal SQL or permission mistakes.
3. As a project owner, I want a first official BTS month early, so that source semantics shape the system before infrastructure expands.
4. As a project owner, I want staged infrastructure adoption, so that final platform requirements remain demonstrable without front-loading them.
5. As an operator, I want explicit bounded refresh requests, so that processing scope and cost are deliberate.
6. As an operator, I want one common refresh interface, so that local and AWS execution do not duplicate business logic.
7. As an operator, I want durable stage results, so that failures are diagnosable.
8. As an operator, I want bounded transient retries, so that recovery cannot consume unlimited resources.
9. As an operator, I want deterministic failures to stop, so that bad data/configuration is not retried blindly.
10. As an operator, I want documented recovery for unknown work, so that absence of evidence is not mistaken for success.
11. As an operator, I want compatible artifact reuse, so that fixed weather inputs need not be reacquired unnecessarily.
12. As an operator, I want manual official-archive import as a fallback, so that fragile acquisition does not defeat the project.
13. As a reviewer, I want immutable source/preparation identities, so that published results are traceable.
14. As a reviewer, I want selected-month replacement, so that source corrections do not double-count operations.
15. As a reviewer, I want repeat-input idempotence, so that reruns do not inflate results.
16. As a reviewer, I want withheld-month addition, so that refresh is demonstrated within the baseline.
17. As a reviewer, I want controlled corrections labeled, so that tests are not represented as observed source revisions.
18. As an analyst, I want explicit scheduled and eligible populations, so that rates mean what they claim.
19. As an analyst, I want unknown outcome flags handled explicitly, so that nulls never silently become false.
20. As an analyst, I want carrier punctuality alongside cancellations/diversions, so that completed arrivals do not conceal disruption.
21. As an analyst, I want scheduled-local temporal patterns, so that delayed actual times do not redefine cohorts.
22. As an analyst, I want airport context, so that location grouping is not presented as responsibility.
23. As an analyst, I want ordered-route comparisons, so that opposite directions remain distinct.
24. As an analyst, I want counts and low-volume warnings, so that sparse groups are not misleading rankings.
25. As an analyst, I want signed mean/median/p90, so that early outcomes and long tails remain visible.
26. As an analyst, I want rates recomputed from counts, so that unequal groups are weighted correctly.
27. As an analyst, I want reported category shares distinguished from total delay, so that unallocated minutes are visible.
28. As an analyst, I want cancellation reasons separate, so that counts and delay minutes are not mixed.
29. As an analyst, I want signed recovery for late departures, so that improvement is measurable without causal claims.
30. As a reviewer, I want source anomalies preserved, so that correctness does not depend on invented repair.
31. As a reviewer, I want stable identifiers and source history, so that changing labels/affiliations do not rewrite operations.
32. As a reviewer, I want justified dimensions, so that SCD patterns are not added merely for display.
33. As an analyst, I want a clearly bounded weather pilot, so that one airport/month is not represented as national coverage.
34. As a reviewer, I want per-variable QC/backward matches, so that stale/future observations are rejected.
35. As a reviewer, I want coverage against all scheduled pilot rows, so that exclusions cannot manufacture acceptance.
36. As an analyst, I want date/episode context, so that correlated flights do not imply independent weather events.
37. As a project owner, I want valid enrichment without a significant effect, so that engineering quality is the objective.
38. As a presenter, I want useful filters/reset, so that the analytical scope is easy to demonstrate.
39. As a presenter, I want coverage and processing dates separated, so that historical results are honestly labeled.
40. As a presenter, I want release-pinned reads, so that publication cannot mix charts from different releases.
41. As a presenter, I want failed required work to retain the last release, so that incomplete results are never silently displayed.
42. As a developer, I want credential-free PR checks, so that ordinary validation needs no live cloud/trial work.
43. As a developer, I want immutable image/task identities, so that reviewed code is identifiable in execution.
44. As a reviewer, I want code deployment separate from refresh, so that merging code does not launch data work.
45. As a security reviewer, I want scoped identities, so that routine work never depends on administrator access.
46. As a security reviewer, I want independent IAM/network validation, so that a green refresh is not security proof.
47. As a reviewer, I want isolated tests, so that fixtures/failures cannot mutate presenter data.
48. As a reviewer, I want real platform tests where necessary, so that mocks are not mistaken for integration evidence.
49. As a project owner, I want measured sizing and covered costs, so that larger resources are not a success criterion.
50. As a project owner, I want preserved evidence and scoped cleanup, so that trial expiry does not erase the showcase.

## Implementation Decisions

The approved architecture details below implement the owner's simplified direction.
Real-platform feasibility evidence and separately approved bounded execution plans
remain required; architectural approval is not a claim those tests have passed.

### D01. Development order and module seam

Order work as **local Python/dbt Core → early real Snowflake/internal stage → first
official month and initial local Streamlit → analytical depth/weather → AWS
integration/execution → deployment automation → final acceptance**. Defer older-AWS-
account selection, verification and configuration until approaching the first
required S3/external-stage or AWS workload integration; do not schedule an early
parallel account/OIDC exercise. None of those checks or GitHub Actions deployment
is a prerequisite for the local path or initial Streamlit work.

Snowflake activation needs separate approval after the local parser/preparation,
dbt project/parse, deterministic fixtures and ready-to-run internal-stage integration
smoke test are in place. Time activation for productive trial use, not account
preflight or speculative setup while local implementation is still missing.

| Module | Interface |
| --- | --- |
| Acquisition/preparation | Explicit official dataset/window or approved import → verified source/prepared manifests |
| Refresh | Request and target → run/stage status, candidate and publication outcome |
| Warehouse build | Exact selected input map → typed dimensional candidate and quality evidence |
| Publication | Complete validated descriptor plus expected authority → committed release or refusal |
| Dashboard read | Pinned released descriptor plus filters → bounded analytical results/metadata |

Local execution is a first-class development/diagnostic adapter, not a second
warehouse engine or an offline replacement application. AWS later runs the same
Python/dbt workload in containers. No separate production business logic per adapter.

### D02. Requests, identities and artifacts

A request names target, explicit months/source versions, relevant reference/weather
versions, code/processing contracts, limits and expected prior release. It cannot
supply arbitrary SQL, commands, roles, resource IDs or download destinations.
Record request, execution, run/stage attempt and publication IDs separately.
Support a full refresh or an explicitly named stage rerun; resolve all prerequisites
from compatible validated artifacts, failing clearly when a dependency is absent.

Source identity uses dataset/partition/content hash, not retrieval time. Prepared
identity adds preparation/schema contract and prepared checksum; loaded identity
includes both. Preserve row ordinal/fingerprint and retrieval provenance. A changed
projection cannot reuse an old loaded artifact just because the ZIP hash agrees.
Select one source/prepared version per month, never count multiple preparations.

Manifests record origins, windows, schema, hashes, bytes/rows, versions, timestamps,
status and outputs. Candidate/release descriptors contain the complete dependency
map and quality report. Identical inputs are reusable only when relevant contracts
remain compatible. Source files/metadata remain outside Git; no secrets in artifacts.

### D03. Acquisition and preparation

Use official BTS monthly marketing archives with a disclosed manual-import fallback.
Inspect members/schema and bounded bytes/disk; preserve original ZIP and prepare
deterministic gzip CSV for loading. ZIP is not a directly loadable CSV format.
Normalize only reviewed header quirks; unexpected columns, width changes or duplicate
normalized headers fail structural checks. Retain required identity, date/time,
outcome, delay/category, airport/carrier, reference-history and diagnostic fields;
the archive preserves all other source values.

Pin CSV/null/quoting/encoding order and gzip metadata/compression contract, keeping
both canonical payload and object checksums. Use create-if-absent completion and
verify existing hashes on replay; names alone are not overwrite protection.
Resolve archive aliases to one requested month. Do not drop source Duplicate=Y or
assume Flights=1 proves distinct physical movements. Production acquisition remains
unauthorized; R06 source research used the owner's additional bounded authorization.

### D04. Early internal staging, later S3 external loading

**Early real integration:** local prepared files → a restricted named Snowflake
internal stage using the Python connector/PUT → COPY into source-shaped raw data →
dbt. This needs Snowflake eligibility/setup approval, **not** AWS/OIDC qualification.
Use content-identified files, no overwrite of accepted artifacts, strict load errors
and exact count checks. Internal stage storage/requests are included in the trial
estimate; clean staged duplicates under the approved lifecycle plan.

**Final AWS path:** preserve originals/prepared/manifests in private S3 and load via
a Snowflake external stage/storage integration with exact role/external-ID trust.
Moving the same prepared bytes through S3 must preserve source/loaded identities
and not duplicate facts. Demonstrate both adapters yield equivalent results. Internal
staging is an incremental development route, not removal of final S3 integration.

Use immutable loaded artifacts; incomplete loads remain isolated and cannot be
accepted from COPY history alone. A corrected month replaces the selected input map.
Rebuild complete isolated marts initially, then measure before optimizing. No unsafe
natural-key MERGE or automatic all-history correction-discovery promise.

### D05. Model, history and table kinds

Use date, stable airport and stable DOT-carrier dimensions, with role-playing
origin/destination and marketer/operator keys, plus a flight fact at one selected
published source row. Technical fact key is a deterministic dataset/source-version/
ordinal hash, not a permanent physical-flight ID. Profile candidate business-key
collisions and swapped reporting; unknown cases require classification, not blind
deduplication. Directional route remains an ordered airport pair initially.

Retain source codes, AirportSeqID, attributes and per-flight affiliations. Consistent
display dimensions are Type 1; use source-native historical versions where correctness
requires them after targeted reference checks. No generalized snapshots/SCD2 merely
to demonstrate a pattern. Weather observations are time-series facts; the pilot
result is exactly one row per selected scheduled operation.
Optional missing references use explicit unknown members with original values and
counts retained; unresolved required identity/time mappings block the affected
candidate. Reference joins may neither drop nor multiply scheduled rows.

**R02 preference:** explicitly configure transient candidate tables and transient
release clones in non-temporary namespaces, initially one-day Time Travel subject
to supported retention/recovery checks. Do not rely on dbt/SQL defaults or clone
transient sources into permanent targets. Small durable control metadata uses an
explicit separate recovery policy. Reconstruction relies on preserved inputs/code;
clone compatibility and limited recovery remain G07 evidence, not claimed tested.

### D06. Metric and quality contracts

Implement the approved PRD definitions unchanged:

| Measure | Population / calculation |
| --- | --- |
| Arrival on-time | Cancelled=0, Diverted=0, known ArrDel15; numerator indicator=0 |
| Cancellation/diversion | Respective known flag=1 / selected scheduled rows |
| Departure delay | Cancelled=0, known DepDel15, diversions included; numerator indicator=1 |
| Signed arrival summaries | Noncancelled/nondiverted known signed arrival delay; mean/median/exact continuous p90 |
| Recovery | Ordinary completions with both signed delays and departure≥15; improvement departure−arrival; recovered arrival<15 |
| Categories | Cancelled=0, Diverted=0, known ArrDel15=1; disclosed compatible subsets for category completeness; reported-minute shares distinct from arrival-delay shares; positive-category counts may overlap; cancellation reasons separately |

Unknown/invalid cancellation/diversion flags block candidate publication under the
initial explicit policy; never coalesce them to false. Preserve structural nulls,
negative early values and N/A denominators. Recompute rates from counts, not subgroup
percentages; never average subgroup quantiles. Default ranking minimum is 100 eligible
observations, displayed/configurable; smaller groups remain inspectable with warnings.
Known outcome/delay indicators must be binary; invalid indicators are critical
quality failures, while missing delay indicators remain explicit metric exclusions.

Critical schema/identity/reconciliation/metric/mapping failures block publication.
Retain reviewed source anomalies unchanged and exclude/flag only affected secondary
calculations, disclosing unallocated/excluded values. Scope exceptions to exact source
evidence; new mismatches are not automatically waived. Provide independent fixture
expectations and exact per-month count reconciliation.

### D07. Denver weather population and joins

Required scope is the full Denver-local January-2025 pilot, including cancellations
and diversions, using ISD temperature/wind/visibility. The existing January UTC
sample alone is insufficient: request the necessary adjacent UTC boundary/lookback
window in later authorized acquisition. Preserve FlightDate/CRSDepTime and original
reporting cohort; do not invent actual cancellation/departure times.

Parse ordinary HHMM as integer hour/minute, never decimal hours; combine the source
date with the scheduled local clock using pinned `America/Denver` timezone data
and preserve the resulting UTC anchor. January has no DST transition. Missing,
malformed or unresolved midnight anchors remain counted and explicitly classified,
not silently repaired or removed. This is not general actual-event reconstruction.

The exact target is scheduled local departure in `[2025-01-01 00:00,
2025-02-01 00:00) America/Denver`; its weather/lookback envelope is
`[2025-01-01 06:00Z, 2025-02-01 07:00Z)`. **R06 is resolved for the inspected source
snapshots:** 24,732 scheduled DEN rows, including 313 cancellations and 69 diversions.
January reporting-date membership and reconstructed scheduled-local membership
agree exactly: intersection 24,732; reporting-only 0; calendar-only 0.

[14 CFR §234.4(a)(10)](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-234/section-234.4)
requires the scheduled operation date; BTS defines CRSDepTime as the local scheduled
clock. The complete December census has 25,905 DEN rows, including 779 on Dec-31;
all December and January DEN clocks are ordinary and valid, with zero scheduled
`0000`/`2400`, missing or malformed clocks. Thus ordinary FlightDate-plus-clock
reconstruction establishes calendar equivalence without a generic midnight rule.
Do not assume `2400 → next day` for future records; rerun the boundary/identity/time
checks on accepted revisions and resolve newly relevant ambiguity before acceptance.

The successful validator-bound range retrieval supersedes the original timed-out
request. Full archive CRC/hash/schema checks and independent reconstruction support
the [source-pinned R06 evidence](#r06-source-evidence) recorded in this specification.
This closes the population decision, not final weather integration acceptance.
Anchors span Jan-1 07:29Z–Feb-1 06:59Z; all 261 January-local rows with February UTC
dates remain included. Obtain the bounded February-UTC weather tail only during
authorized implementation; no December weather, denominator reduction or new scope.

Decode aviation reports and field-specific sentinels/QC explicitly; initial ISD
QC whitelist {1,5} must match the pinned format. Collapse identical accepted station/
time/variable values with provenance; conflicting accepted ties fail rather than
permit nondeterministic ASOF results. Join each variable independently to its latest
accepted observation at/before scheduled departure, inclusive age 0–3600 seconds.
Expose older-good fallback, different variable times, stale/rejected/missing status.

Coverage is **≥95% for each variable over all scheduled pilot rows**, not only
matchable/operated rows. Future matches and row multiplication must be zero. Show
ages, counts, cancellation/noncancellation coverage and date/episode concentration.
Bands and low-date warnings are presentation choices, not significance/publication
requirements. No compound weather, causal claims, extra airports/years or GHCNh switch.

### D08. Lock-first control and atomic release publication

**R01 approved direction:** one short explicit transaction first makes a real guard
write by immutable target identity to acquire the control-row write lock; only then
reads/validates current owner, attempt/fence, cancellation/deadline and publication
epoch in subsequent statements. Apply that order to claim, publish, cancellation
and explicit recovery. Use one transaction owner, short lock timeout, exact singleton/
registry cardinality and explicit whole-transaction rollback on any error. Do not
hold a transaction across jobs/DDL, use standard-table SELECT FOR UPDATE, or rely
on unenforced standard PK/UNIQUE constraints. Real concurrent-session tests remain
mandatory before treating the protocol as proven.

Build in isolated work namespaces. Seal only after all candidate writes/queries
finish. Publisher snapshots allowlisted self-contained tables into a create-only
release schema, with explicit compatible transient kinds and release-local views;
no source-bound work views, inherited broad grants or mutable dependencies. Validate
the actual frozen full result set before selection. Builder has no serving writes;
reader has database/schema USAGE and SELECT on named released views only. Give
publisher exact candidate-container USAGE/SELECT and destination creation/ownership,
not global MANAGE GRANTS or a builder role inheritance shortcut.

Perform all snapshot/grant DDL before the publication transaction. Under the lock,
insert/verify the immutable release registry and atomically change the active
descriptor/epoch. Reconcile lost COMMIT acknowledgment by exact publication identity;
never blindly repeat or reuse a published name. Routine publication cannot change
old release contents. Owning-role immutability is a trusted-job invariant, not WORM.

Keep execution fence separate from publication epoch. Duplicate requests return
existing results, not a second writer. Uncertain work leaves a nonexpiring run claim
blocked until explicit recovery verifies terminal tasks/queries/transactions. No
automatic takeover. Normal success/failure handling may retire its authority and
release the claim once all prior data-capable work is terminal; the final control
tail then only records status/exits. It does not wait for its own future STOPPED
state and cannot publish again under the retired generation. A crash before retirement
needs recovery; after committed publication it is a status/cleanup issue, not rollback.

Reader resolves active pointer and complete descriptor once, pins it through every
query/cache key, and uses only release-local objects. Retain active/previous and a
reviewed minimum 24-hour retired-reader window; expired tokens require explicit
reload, not mixed fallback. Older complete session-visible metadata is safe; no
instantaneous global visibility guarantee. A failed required stage retains the
entire previous validated release; initial failure returns unavailable.

### D09. Bounded execution and ordinary recovery, not a watchdog platform

**Local:** one Python refresh runner invokes load/dbt/validation/publication with
bounded subprocess/client/server SQL deadlines, durable stage artifacts and useful
errors. Use the same workload/manifest interfaces later in AWS.

**AWS:** Step Functions Standard coordinates finite standalone ECS jobs with .sync,
sequential approved partitions, a combined load/dbt/validate job and a separate
publisher/control job. Ordinary Retry/Catch paths classify bounded transient errors,
record failure and attempt scoped cleanup. No classifier Lambda, periodic EventBridge
watchdog, monitoring warehouse, autonomous finalization or recurring SQL polling.
The managed EventBridge rule required by ECS .sync is an integration dependency,
not a project safety scheduler.

Require essential-container success **and** a matching completed result manifest.
.sync does not return application stdout: use a small explicit S3 result bridge
where branching needs application outcomes. Keep control results≤16KiB and workflow
envelopes≤64KiB; large reports stay outside state. Persist launch intent/attempt/
task/query IDs, honor supported transport idempotency and reconcile uncertain launches
before a new attempt. No routine redrive; deliberate reruns use new validated attempts.

Initial reviewable bounds: one data-mutating attempt per target; at most one extra
transient attempt; acquisition 5-minute total per partition, warehouse 45-minute
total and publication 5-minute total across attempts; workflow maximum 4 hours.
Set integration timeout/grace and every SDK/HTTP/SQL/queue/lock limit from remaining
absolute time, not reset budgets. Initially use small compatible Linux tasks and
two dbt threads; actual CPU/memory/partition limits are set by measured G06 envelopes.
Warehouse statement ceilings plus per-session remaining-time limits bound server
work; client/subprocess timeout alone does not stop a detached Snowflake query.

**Uncertain work:** aborted workflows, lost clients, missing manifests or failed
cleanup become RECOVERY_REQUIRED. StopExecution/.sync cancellation is best effort;
ECS STOPPED is not SQL/transaction termination proof. Leave publication authority/
claim blocked, preserve status, and run the documented scoped recovery when attended.
Recovery inspects the actual execution/tasks/query IDs, stops remaining known work,
reconciles a possibly committed release, then clears only the matching retired
authority. Use the originating workload identity for its own query/transaction
recovery where supported; no always-on privileged canceller or broad warehouse abort.
If termination cannot be verified, do not start another mutation or claim recovery.

Workflow state, publication outcome and cleanup status are separate. Ordinary
terminal paths persist run/stage results; if external abort prevents a final write,
Step Functions/local evidence is authoritative for execution until the operator's
explicit reconciliation records durable terminal status. No promise of autonomous
repair, instant orphan detection or an exact hard billing cap. G06 must reserve
for bounded SQL/task orphan exposure and attended recovery under strict $0. If
that exposure cannot be covered, the run is not authorized. A later safety timer
would require evidence of need and separate review, not automatic scope restoration.

### D10. Final AWS networking and storage

The proposed minimal final option remains short-lived public-IP tasks in one
dedicated Stockholm VPC/subnet with internet gateway, zero inbound rules, no listener,
SSH/ECS Exec, NAT or load balancer, and an S3 gateway endpoint where useful. Private
interface endpoints alone cannot reach BTS/NOAA/public Snowflake and add a persistent
cost floor; IPv6 is not assumed end-to-end compatible. Explain outbound/exfiltration
limits honestly; this is not private-only networking or a domain allowlist.

S3/ECR/logs/Secrets Manager/Step Functions/ECS dependencies are added only after
target qualification. Original/prepared/versioned artifacts, test data and state
have separate access scopes; private buckets, HTTPS, owner-enforced access and
SSE-S3 by default. No duplicate curated lake or unnecessary continuously running job.

### D11. Minimal identity and authentication separation

| Identity | Scope |
| --- | --- |
| Local builder / later warehouse task | Read/load accepted inputs; create/test candidates; no serving/control publication writes |
| Publisher/control | Exact completed candidate reads, serving snapshots/validation and reviewed control operations; no cloud administration |
| Local dashboard | Named released views and sanitized metadata only |
| Later acquisition task | Approved input/report objects; no Snowflake publisher secret or Terraform state |
| ECS execution role | Agent ECR pull/log delivery; not the union of all workload credentials |
| Step Functions role | Approved project task families, cluster and service-constrained exact task/execution PassRole; required .sync event-rule permissions |
| Image/release deployment identities | Trusted ECR push and restricted Terraform release changes; no direct RunTask/StartExecution |
| Approved operator/recovery | Bounded target start/status/stop and workload-specific recovery; no admin fallback or other-target access |

Early Snowflake credentials use an approved protected local mechanism outside Git;
service-user key pairs are the compatibility-first proposal. No secrets in code,
images, CLI arguments, logs, manifests or Terraform state. Later AWS workload keys
are seeded outside Terraform into exact restricted secrets; infrastructure manages
metadata/public keys/access, not plaintext values. Human and machine access remain
distinct. No permanent AWS access keys. Pin and test actual client authentication;
do not assume AWS OIDC automatically authenticates Snowflake or add experimental
WIF migration to the baseline.

### D12. Terraform adoption and single ownership

Terraform is a final required deliverable, **not an early warehouse prerequisite**.
Early separately approved Snowflake bootstrap creates only needed logical objects,
roles and limits and records an ownership/import inventory. Later Terraform imports/
adopts the agreed static objects rather than recreate the warehouse or destroy data.
Until AWS qualification, no remote S3 backend is required for local Python/dbt work.

Final ownership: Terraform manages AWS storage/network/security/ECR/tasks/workflow,
Snowflake databases/static schemas/roles/users/integration/warehouse/monitor; versioned
control migrations own control-table/procedure DDL and singleton initialization;
the pipeline owns data/runtime schemas and DML. No dual Terraform/migration owner.
Separate scoped platform versus application-release state only where it protects
privileges; do not build a generic multi-root platform framework.

Use a restricted versioned S3 state backend with native lockfile support in a
reviewed Terraform release≥1.10, SSE-S3 and separate state/lock permissions. Bind
backend and every provider to the one approved account, with clean initialization
and protected plans/state. State migration does not move cloud resources across
accounts. A target change needs fresh deployment/adoption, not stale state plus new
credentials. Protect any temporary bootstrap state and document its eventual owner.

Terraform alone registers ECS task revisions and workflow versions from reviewed
image digests. Retain old task/image/workflow dependencies while referenced or needed
for rollback; do not silently adopt latest revisions or mask image drift. Partial
apply is recoverable from the last usable deployment inventory, not automatically
rolled back. Platform output manifests bind account/region/contract and named objects.

### D13. Simple deployment and GitHub Actions

Credential-free PRs run tests/lint, dbt parse, container checks and backend-disabled
Terraform validation as available. Package/provider/build networks are distinct
from explicitly network-disabled fixtures. No cloud/Snowflake tokens on PRs, live
data downloads or applies; do not execute untrusted code through privileged triggers.

Approved merges publish immutable ECR digests then use Terraform to update only
the approved image/task/workflow release. No data refresh on merge. OIDC trust needs
exact actual repository/subject/audience and enforced branch/event rules; private
GitHub plan/protection/billing and the alternative AWS OIDC path remain G01/G08.
No paid upgrade, permanent-key workaround or implied repository publication.

**R04:** prefer deferring deployment while an authorized refresh is active, using
the ordinary single-operator/batch workflow; do not add a cross-system mutex.
Keep executing workflows on their recorded immutable task/image versions. Publish
a workflow version and record its ARN in the approved deployment manifest; subsequent
refreshes start that version explicitly, avoiding eventual propagation of an
unqualified update. Existing execution definition/role-ARN snapshots remain intact.
Retain their permissions/dependencies until terminal; do not change platform IAM/
network/schema contracts inside an ordinary image release. An observed-idle check
is operational coordination, not an atomic lock; pinning/retention supplies safety
if starts and a deferred deployment overlap. Test that narrow case, not a new HA
deployment-admission protocol.

Use bounded approved task-family/revision launch permissions with fixed cluster and
role restrictions to avoid platform IAM edits on every image revision; Terraform
release CI cannot change those roles. Its distinct workflow PassRole requirements
are service-constrained. Checked saved plans reject unexpected role/command/secret/
network/logging/graph changes. Deployment is trusted code distribution even without
direct launch rights. Rollback promotes a retained digest/version; it is not a data
rollback. No aliases, blue/green platform or autonomous deployment recovery required.

### D14. Local dashboard and release-aware queries

Use a thin Streamlit reader with date/carrier/origin/destination/ordered-route filters,
reset/filter summary, methodology/quality view, and six analytical areas plus the
fixed weather pilot. Page/chart arrangement stays flexible; no required exports,
raw downloads or public hosting. Display unknown/excluded counts, ranking threshold,
source perspective and coverage versus processing/publication times.

Resolve one released descriptor per render; parameterize SQL values and allowlist
its schema. Query aggregates in Snowflake, not all flights into pandas. Cache keys
include account/target/release/query version and all result-affecting filters;
explicit analytical TTL initially 15 minutes and short metadata TTL 15 seconds. Disable
hidden indefinite query caching. Retired/expired descriptor errors require reload,
not partial chart fallback. Exact quantiles use eligible values, not subgroup averages.
Record cold/warm responsiveness and optimize before resizing; no production SLA.

### D15. Tools and environment

Use Python 3.12, pytest, Ruff, dbt Core/Snowflake adapter, Snowflake Python connector,
Streamlit/AppTest, and later Docker/Terraform/GitHub Actions. Pin reviewed compatible
released versions, dependencies/providers and images during authorized setup; no
installation now. dbt parse is credential-free project validation, not proof the
warehouse accepts SQL. Use real Snowflake for SQL/integration evidence, not a second
local SQL engine. Newer Fusion/platform features are not assumed to exist in Core.

### D16. Cost and finite lifecycle

Strict **$0 out of pocket** applies independently to Snowflake, AWS and GitHub. AWS
G01 is evaluated before AWS provisioning, not before local or authorized Snowflake
work or initial Streamlit. Schedule G01 only when approaching the first required
AWS integration, not as parallel early work. The older paid account's approximately
$160 is owner-reported; then verify exact
usable credits/expiry, eligible charge/invoice/tax categories, shared consumption,
region, IAM/OIDC and all proposed dependencies before selecting it. Prefer the whole
AWS footprint in one approved account. Credits/reserves/alerts do not cap paid cash
liability; uncovered or uncertain spending keeps authorization blocked.

Start Snowflake small, suspended, with auto-suspend 60 seconds, query/stage limits,
custom roles and a small nonresetting resource monitor configured before loads.
Five compute credits with 50/75/90% notify/suspend/immediate thresholds remains an
initial review proposal, not a lifetime estimate/hard cap. Storage and excluded
costs need separate allowance. Verify trial terms/expiry before authorized activation.

Estimate each phase's worst-case work, retry/orphan recovery, retained raw/candidate/
clone/state/image/log storage, transfer and evidence/cleanup. Keep a conservative
reserve (initial proposal 25% or cleanup/recovery need, whichever greater) without
claiming it reserves actual shared credits. No periodic watcher or idle SQL polling
cost. No automatic size/quota/credit-limit increase. Measure a small Snowflake case
and an AWS case separately before larger runs; full rebuild feasibility is G06.

Preserve raw versions/manifests and sanitized evidence through presentation. Proposed
log retention 7 days and active/previous releases plus 24-hour reader compatibility
are lifecycle choices to cost/check before use. Never expire dependencies still
referenced by running work. Before entitlement expiry, capture results/diagrams/logs,
verify actual stopped tasks/queries and perform only explicitly approved scoped
cleanup. No permanent availability or repeated-trial eligibility promise.

## Testing Decisions

### T01. Primary seam and independent expectations

Test refresh → validated release through observable results, status/provenance and
reader consistency. Add focused parsing/eligibility/QC/time/control tests where
useful. The repository has no implementation test prior art; research profilers
provide edge-case evidence, not production modules. Expected fixture counts/ratios/
quantiles/matches must be independent of production calculations.

### T02. Test levels and genuine prerequisites

| Level | Evidence / prerequisites |
| --- | --- |
| Local Python/dbt validation | Fixtures, parser/time/manifest/control tests, dbt parse, UI fixture tests; no AWS account or active Snowflake needed |
| Early real Snowflake | Local implementation and runnable smoke test ready, then separately approved trial/setup and cost/tool gates; local dbt Core/internal-stage COPY, real SQL, roles, transient clones, lock-first/concurrency and pinned reads; **no AWS/OIDC dependency** |
| First official month / initial Streamlit | Approved source acquisition/import and source-quality checks; real Snowflake primary metrics/reference/source reconciliation and local released-result presentation; **no AWS account/OIDC/GitHub Actions deployment dependency** |
| Later AWS/CI | Qualified account/funding/trust and bounded cloud plan; real S3/external stage, ECS/.sync/retries/recovery, Terraform and merge promotion tests |
| Final acceptance | Complete 36 months, six analyses, full weather pilot, replay/correction/failure safety, independent security/delivery/cost and preserved evidence |

No simulated SQL or green PR clears real-platform gates. Early test releases are
clearly partial/synthetic; they do not waive final required modules/coverage.

### T03. Required behavioral cases

Test repeat inputs and changed preparation; month correction versus clean rebuild;
14/15-minute/negative/null/zero-denominator boundaries; cancellations with departure
values; diversions with specialized arrival fields; unknown flags; 99/100 ranking;
category overlap/unallocated exceptions; signed recovery and exact continuous p90;
reversed routes and reference joins; midnight/2400/adjacent dates; QC ties/fallback,
ages 0/3600/3601 seconds/future and all-pilot coverage; release changes mid-render; errors at
each transaction step; duplicate claim, lock contention, stale attempts, lost
commit; failed required stages; bounded retry/timeout; uncertain client/launch/query
termination; completed publication followed by bookkeeping failure; explicit recovery.

Counts/keys reconcile exactly; fractions/continuous quantiles use documented
absolute tolerance 10⁻⁶ before rounding. Example oracle: ordinary arrival delays
−10, 0, 14, 15, 60 give mean 15.8, median 14, p90 42 and on-time 3/5. Signed improvements
6, 15, 0 give mean 7, median 6, p90 13.2; these are labeled fixtures, not observed BTS results.

### T04. Independent infrastructure and delivery checks

Verify eventual Terraform ownership/import plans, backend/provider account binding,
state locks/protection, real positive/negative IAM/PassRole/target isolation, routes/
no inbound/NAT, image/task/workflow version identity/retention, trusted OIDC/PR denial,
approved merge with no data launch, partial-apply recovery and old/new-run version
behavior. Check effective server/client/runtime deadlines and attended stop/recovery
without assuming workflow stop means no compute. Verify actual applicable credits,
expiry and covered lifecycle charges, not just alerts or a green data run.

### T05. Final PRD acceptance mapping

| Outcome | Required evidence |
| --- | --- |
| AC-01 | Final Terraform-managed agreed infrastructure and imported bootstrap inventory, region/isolation/security checks |
| AC-02 | Credential-free PR checks, approved digest/task/workflow promotion and no automatic data execution |
| AC-03 | Coordinated observable refresh and withheld-month addition to complete coverage |
| AC-04 | Idempotent same-input replay, traceable correction and expected/rebuild equivalence |
| AC-05 | Atomic publication, last validated release retained on failure, pinned reads and isolated tests |
| AC-06 | All six analyses, approved metric contracts, independent reconciliation and full-pilot≥95% per-variable/≤60m/zero-future/zero-multiplication |
| AC-07 | Measured sizing/credits, effective IAM/network/secrets/runtime limits, recovery evidence and no out-of-pocket charges |
| AC-08 | Owner-reviewed explanation, diagrams/methodology/operations and sanitized pre-expiry presentation evidence |

Traceability: DATA-01–08→D02–05; MET-01–07/ANA-01–06→D06/D14;
WX-01–04→D07; DASH-01–04→D08/D14; PIPE-01–06→D02/D04/D08–09;
INF-01–06→D04–05/D10–12; CI-01–04→D12–13; COST-01–04→D09/D16;
EVID-01–03→T05 and lifecycle documentation. Early adapters do not remove any final
PRD outcome.

## Out of Scope

Retain the PRD non-goals: production HA/public availability, real-time/predictive/
causal or passenger analytics, fairness models/composite score, national weather,
unjustified SCD2, exports/raw browsing, automatic 2026/history discovery, Kubernetes,
duplicate environments/lakes, NAT and unnecessary always-on infrastructure.

Additionally exclude the v0.3 periodic watchdog/safety Lambda, autonomous orphan
recovery/finalization framework, cross-system deployment mutex and admin-capable
query canceller. Optional future safety infrastructure needs demonstrated need
and separate approval. No feature/acceptance is silently weakened to remove it.

## Further Notes

### Gates: apply them to the phase they genuinely constrain

| Gate | Required evidence / scope |
| --- | --- |
| G01 | **Deferred until approaching first required AWS integration**, before any AWS configuration/provisioning: older paid target identity, actual credits/expiry/charge eligibility/tax/shared usage, IAM/OIDC/SCP controls, Stockholm/services/quotas and target approval. No early parallel verification. Original Free Plan OIDC reads are verified denied; alternative remains unverified. Does not block local Python/dbt Core, internal-stage Snowflake, first BTS month or initial Streamlit. |
| G02 | Before **Snowflake activation/setup**: local implementation/fixtures/dbt parse and ready-to-run internal-stage smoke test, then owner timing approval, trial/region/terms/credits/auth and bounded integration plan. Activate only for productive implementation use; no activation now. |
| G03 | Before final source/pilot acceptance: official acquisition/header/QC/unit/tie and full-window join checks. R06 date-boundary interpretation is resolved for inspected snapshots; revalidate membership on accepted source revisions, not an open architecture decision. |
| G04 | Before baseline acceptance: whole-period identities/swaps/row counts/outcome patterns/aliases and exact reviewed exceptions. Not all36 months needed to start one-month development. |
| G05 | Before affected history/mapping acceptance: actual reference/version changes, source validity and station/time mapping; no arbitrary SCD or lost facts. |
| G06 | Phase-specific cost/runtime/retention envelope: early local/Snowflake first, AWS separately later; measure before full builds and demonstrate bounded uncertainty/recovery reserve. No hard-cap claim. |
| G07 | Real **Snowflake** lock-first/rollback/singleton/registry/replay/cancel/grant/transient-clone/pinned-read tests. Not gated by Terraform/ECS/GitHub qualification. |
| G08 | Relevant tooling/client/provider compatibility and authentication/installation approval; GitHub plan/subject/billing checks apply when CI deployment is introduced, not to initial dbt work. |
| G09 | Execution-adapter-specific evidence: local process/SQL limits and manual recovery first; ECS/.sync/result/launch/stop/retry/old-version tests before AWS runs. No periodic reconciler qualification. |
| G10 | Specification approval, reviewed ticket bodies/batches and separate bounded external-effect plans. Passing a gate is not itself permission to activate/provision/run/publish. |

### Recorded decision status

- **R01:** lock-first approach approved; actual concurrent behavior remains G07.
- **R02:** explicit transient candidate/release preference approved for this revision;
  clone/retention/reconstruction compatibility still needs real evidence.
- **R03:** minimal bounded execution, ordinary failure handling and explicit attended
  recovery replace the periodic/autonomous control proposal. Residual orphan/status
  uncertainty is documented, not hidden or claimed automatically repaired.
- **R04:** simple version retention/recorded workflow starts and deferred deployment;
  no cross-system mutex. Stable platform policies and migration ownership remain
  reviewed controls, not a new generic deployment platform.
- **R05:** paid AWS target likely but unapproved. Defer selection/verification/
  configuration until approaching first required AWS integration; no early parallel
  preflight or AWS/OIDC/deployment prerequisite for local warehouse/Streamlit work.
- **R06 resolved:** scheduled date plus ordinary DEN local clock, retaining full
  calendar January. Complete Dec-31/January evidence gives 24,732 members and zero
  reporting/calendar differences. Repeat checks on source revisions; no generic
  `2400` assumption or permanent hard-coded count.

### Evidence and review workflow

The planning review reports remain historical evidence, not current requirements
to retain the removed machinery. This revision records the owner's approved
simpler direction. No new account probes or live integration tests were
performed. New data work was limited to the explicitly authorized R06 December
retrieval and local December/January boundary census; no weather expansion. The
original failure, revised bounded method and successful source evidence are retained.

Official documentation supporting the changed paths:

- [Snowflake PUT/internal staging](https://docs.snowflake.com/en/sql-reference/sql/put)
  and [loading overview](https://docs.snowflake.com/en/user-guide/data-load-overview).
- [Snowflake transactions](https://docs.snowflake.com/en/sql-reference/transactions),
  [clone/table kinds](https://docs.snowflake.com/en/user-guide/tables-temp-transient),
  [parameters](https://docs.snowflake.com/en/sql-reference/parameters) and
  [query cancellation](https://docs.snowflake.com/en/sql-reference/functions/system_cancel_query).
- [Step Functions updates](https://docs.aws.amazon.com/step-functions/latest/apireference/API_UpdateStateMachine.html),
  [version-qualified starts](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-state-machine-version.html)
  and [ECS .sync/cancellation](https://docs.aws.amazon.com/step-functions/latest/dg/connect-ecs.html).
- The approved PRD's BTS/NOAA/FAA sources and existing sample reports remain
  evidence, not proof of unexamined complete-year/history behavior. The narrow
  R06 boundary comparison below was separately verified.

### R06 source evidence

The selected official source snapshots establish the D07 population decision:

| Snapshot | ZIP SHA-256 | National rows | DEN rows |
| --- | --- | ---: | ---: |
| December 2024 | `86b6fccb118ac9c8df435b9aeb674f1053873d48cf958248457d03557c263a3f` | 631,944 | 25,905 |
| January 2025 | `0feaabdbc9e4bd851ef717f342678cdcc5ea0822dd706359aab030bb1a5d1c24` | 599,013 | 24,732 |

Official archives: [December 2024](https://www.transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2024_12.zip)
and [January 2025](https://www.transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2025_1.zip).
The complete CSV reads verified CRCs, matching 119-named-field schemas plus trailing
empty field, no row-width errors and no DEN code/stable-ID disagreement. Every DEN
row uses `DEN|11292|1129202`; both months contain zero scheduled midnight, missing
or malformed clocks. Dec-31 has 779 DEN rows; Jan-1 has 816 and Jan-31 has 810.
Calendar/reporting sets intersect on all 24,732 January rows with zero differences.
Independent reconstruction agrees. Of those rows, 313 are cancelled, 69 diverted
and 261 have February UTC anchors; no outcome or weather-match exclusion was used.

Scheduled-date semantics follow [14 CFR §234.4(a)(5),(10)](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-234/section-234.4),
the [BTS marketing field definitions](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGK)
and [Directive 39, effective 2025](https://www.bts.gov/explore-topics-and-geography/modes/aviation/number-39-technical-directive-reporting-time).
Live eCFR amendment history was checked; an independently dated historical-page
fetch was blocked. The reviewed text does not settle generic `2400` date attachment,
which is unnecessary for these ordinary-clock snapshots. On revisions rerun D07's
checks; this evidence neither fixes the denominator forever nor proves final
full-window weather integration. Detailed acquisition ledgers and boundary samples
remain planning evidence in the separate workspace, not a runtime or standalone
repository dependency.

Detailed tickets and implementation batches are the next review gate. Publication
and external-effect plans require their own approval. Early Snowflake bootstrap
is a documented bounded exception with later Terraform adoption, not permanent
unmanaged infrastructure. Preserve all G01–G10 evidence and authorization gates.

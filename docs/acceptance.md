# Acceptance evidence map

**Status: final validation in progress; not a completion or owner-acceptance claim.**
The approved [specification](specifications/airline-delay-intelligence.md#t05-final-prd-acceptance-mapping)
defines the acceptance outcomes. This index maps implementation evidence and
remaining gates without weakening those outcomes.

The reviewed [delivery qualification summary](evidence/delivery-qualification.json)
records the latest checkpoint. The earlier [qualification snapshot](evidence/qualification-summary.json)
predates resolution of its GitHub/tooling prerequisites. Neither is a live inventory
or owner-acceptance statement.

| Outcome | Existing evidence | Remaining final gate |
| --- | --- | --- |
| AC-01: managed infrastructure | [Adoption](terraform-adoption.md) and [completed owner import](snowflake-owner-adoption.md): protected separate state; all three SERVICE users imported; official-provider normal plan clean at fifteen Snowflake instances | Owner review of unsupported account-monitor attachment coverage and refresh-only last-login metadata exception; no remaining user imports |
| AC-02: code delivery without data start | [Delivery](delivery.md): actual credential-free PR checks, protected public-repository environment/OIDC, direct-launch denials, checked-merge promotion, overlap, code rollback and partial-apply recovery; strengthened-guard promotion/replay passed at version 7 | Owner review; public visibility explicitly approved |
| AC-03: coordinated refresh and completion | [Baseline](baseline.md): actual withheld-month addition; [cloud](cloud-jobs.md): full-module workflow, four stopped tasks, 810 terminal queries and independent 36-month/weather reconciliation | Remaining failure/delivery qualification is separate; complete positive-cloud path is verified |
| AC-04: repeat/correction correctness | [Baseline](baseline.md), [analytics](analytics.md): local replay, changed preparation and controlled correction/rebuild comparison; [cloud](cloud-jobs.md): exact full-input replay, supported same-name/input launch reconciliation and successful next admission | Owner review; no new positive-path correctness gap identified |
| AC-05: atomic/pinned/failure safety | [Cloud recovery](cloud-recovery.md): real abort, detached SQL/transaction, post-commit reconciliation, next admission and stale fencing; [delivery](delivery.md): actual overlap, rollback and partial recovery; prior complete cloud release remains readable | Owner review; synthetic retry-engine injection is not a real S3 outage |
| AC-06: complete analytics/weather | [Baseline](baseline.md), [secondary analytics](secondary-analytics.md), [weather](weather.md), [cloud](cloud-jobs.md): independently reconciled complete cloud result; final real dashboard passed six views, DEN/reset and production pin | No positive-path data gap remains; overall acceptance still requires other outcomes |
| AC-07: security/runtime/covered costs | [Adoption](terraform-adoption.md), [cloud](cloud-jobs.md), [delivery](delivery.md): actual scoped-role/OIDC denials, no ingress, measured limits and cumulative reserve; final audit found no active tasks/workflows or originating transactions; [image assessment](image-security.md) | Owner review of retained findings and finite funding; credits are not a hard cash cap |
| AC-08: explanation and preserved evidence | [Presentation](presentation.md), [sanitized summary](evidence/qualification-summary.json), [cleanup proposal](cleanup-plan.md), existing methodology/runbooks and source evidence | Owner walkthrough/review and evidence for outstanding delivery gates; cleanup remains separately unapproved |

## Known external prerequisites

- The owner confirmed intentional public visibility on 2026-11-03 and authorized
  publication after a secrets/state/sensitive-evidence audit. This prerequisite is
  resolved; actual protected delivery still requires qualification.
- Three Snowflake user imports completed under the owner-controlled boundary on
  November 4; keys/defaults/grants/parameters remained unchanged, and the official
  normal plan is clean. The pinned provider still cannot read the account-monitor
  attachment; read-only verification passed without changing the binding. Refresh-only
  reports only moving last-login observations and exits 2, so its literal clean gate
  remains unmet. [Exact outcome and exceptions](snowflake-adoption-gap.md).
- Terraform 1.13.4 has been restored with owner approval from HashiCorp's release
  site. Its checksum manifest has a verified HashiCorp signature, the archive
  checksum matches and the executable reports the pinned version. This prerequisite
  is resolved; restoration itself does not authorize unrelated infrastructure.
- The three HIGH image findings have been [investigated](image-security.md).
  Stable Debian offers no newer candidate for the affected packages; preserve
  findings and bind the assessment to the tested/scanned promoted digest.

These are genuine publication/security and privileged-adoption prerequisites, not
requests for routine implementation approval. Independent cloud, local testing and
presentation preparation can continue while they are unresolved.

## Final batch disposition

- **16:** Complete cloud positive path, exact replay and retained old/new pins qualified.
- **17:** Actual public-repository PR/merge CI, scoped OIDC, effective denials,
  immutable promotion, code rollback and partial-apply recovery qualified.
- **18:** Abort, detached SQL/transaction, post-commit, next admission and stale
  fencing qualified. AWS retry/timeout-engine tests use explicit synthetic errors;
  no naturally occurring S3 outage is claimed.
- **19:** Consolidated evidence is ready for owner review, **not full acceptance**:
  AC-01 still has the attachment coverage/refresh-metadata exceptions described above, and known
  image findings/funding limits remain disclosed.
- **20:** Presentation, diagrams, sanitized evidence and cleanup proposal are prepared.
  Owner walkthrough/acceptance remains outstanding; no destructive cleanup performed.

The prior platform/application no-change evidence covers 53/four instances. The
November 4 owner import has an official-provider normal no-change plan covering
**fifteen Snowflake instances**, including all three users. No provider-managed
account attachment or exit-zero refresh-only result is claimed. Final prior SQL scope covers 27 originating sessions with zero open
matching transactions and no active test claim. Production remains 36 months and
22,562,477 rows; all task revisions 3–7 remain ACTIVE. The final warehouse observation
is SUSPENDED, X-Small, with zero running/queued statements and auto-suspend 60 seconds.

## Interpretation limits

Offline tests are not cloud integration; image registration is not a data run;
ECS STOPPED is not proof that SQL/transactions terminated; Basic scan COMPLETE is
not a clean vulnerability scan; rounded account-monitor readings are not final
billing. Controlled synthetic corrections are not observed official revisions.
Preserved evidence is not a promise of permanent application availability.

The final report must name every unmet outcome above, exact accepted code/source/
image/workflow/release identities, actual tests and exceptions. Do not mark tickets
16–20 complete merely because a subset of this table is green.

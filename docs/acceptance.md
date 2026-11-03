# Acceptance evidence map

**Status: final validation in progress; not a completion or owner-acceptance claim.**
The approved [specification](specifications/airline-delay-intelligence.md#t05-final-prd-acceptance-mapping)
defines the acceptance outcomes. This index maps implementation evidence and
remaining gates without weakening those outcomes.

The reviewed [sanitized qualification summary](evidence/qualification-summary.json)
captures the 2026-11-03 evidence checkpoint, not a live inventory or final acceptance.

| Outcome | Existing evidence | Remaining final gate |
| --- | --- | --- |
| AC-01: managed infrastructure | [Adoption](terraform-adoption.md): protected separate AWS/Snowflake static state, preserved bootstrap inventory, scoped platform/application ownership | Deferred Snowflake service-user/account-monitor adoption needs an approved infrastructure identity |
| AC-02: code delivery without data start | [Delivery](delivery.md): credential-free workflow, verified action commits, local checks, immutable operator promotion and plan guards | Actual GitHub checks, enforced private-repository protection/OIDC trust, deployment identity permission tests and retained-version delivery qualification |
| AC-03: coordinated refresh and completion | [Baseline](baseline.md): actual withheld-month addition; [cloud](cloud-jobs.md): full-module workflow, four stopped tasks, 810 terminal queries and independent 36-month/weather reconciliation | Remaining failure/delivery qualification is separate; complete positive-cloud path is verified |
| AC-04: repeat/correction correctness | [Baseline](baseline.md), [analytics](analytics.md): local replay, changed preparation and controlled correction/rebuild comparison; [cloud](cloud-jobs.md): exact full-input replay reused the identical descriptor with one admission task | Remaining uncertain-launch/recovery cases |
| AC-05: atomic/pinned/failure safety | [Cloud recovery](cloud-recovery.md): real abort, detached SQL/transaction, post-commit reconciliation, next admission and stale fencing; prior complete cloud release remains readable | Remaining delivery overlap/rollback qualification is separate |
| AC-06: complete analytics/weather | [Baseline](baseline.md), [secondary analytics](secondary-analytics.md), [weather](weather.md), [cloud](cloud-jobs.md): independently reconciled complete cloud result; final real dashboard passed six views, DEN/reset and production pin | No positive-path data gap remains; overall acceptance still requires other outcomes |
| AC-07: security/runtime/covered costs | [Adoption](terraform-adoption.md), [cloud](cloud-jobs.md): scoped roles/secrets/network, measured finite tasks, durable identities, cumulative monitor/reserve accounting | Remaining actual CI permission and cloud failure/exposure cases; current funding/expiry and final terminal inventory |
| AC-08: explanation and preserved evidence | [Presentation](presentation.md), [sanitized summary](evidence/qualification-summary.json), [cleanup proposal](cleanup-plan.md), existing methodology/runbooks and source evidence | Owner walkthrough/review and evidence for outstanding delivery gates; cleanup remains separately unapproved |

## Known external prerequisites

- The owner confirmed intentional public visibility on 2026-11-03 and authorized
  publication after a secrets/state/sensitive-evidence audit. This prerequisite is
  resolved; actual protected delivery still requires qualification.
- Current Snowflake workload roles cannot faithfully expose the provider metadata
  required for service-user/account attachment adoption. Do not remove
  `prevent_destroy`, suppress TYPE drift or add broad workload privileges to obtain
  a green plan. Use an explicitly approved infrastructure identity and reviewed
  import/no-change plan.
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

## Interpretation limits

Offline tests are not cloud integration; image registration is not a data run;
ECS STOPPED is not proof that SQL/transactions terminated; Basic scan COMPLETE is
not a clean vulnerability scan; rounded account-monitor readings are not final
billing. Controlled synthetic corrections are not observed official revisions.
Preserved evidence is not a promise of permanent application availability.

The final report must name every unmet outcome above, exact accepted code/source/
image/workflow/release identities, actual tests and exceptions. Do not mark tickets
16–20 complete merely because a subset of this table is green.

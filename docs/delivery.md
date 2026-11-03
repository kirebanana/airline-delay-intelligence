# Code delivery and data execution

**Status: local validation and operator promotion qualified; GitHub execution and
protected OIDC deployment remain pending.** On 2026-11-03 the owner confirmed that
the repository is intentionally public and authorized verified publication.
Audit committed history and new artifacts for secrets, state and sensitive evidence
before pushing; do not change repository visibility.

## Credential-free validation

`.github/workflows/validate.yml` runs on pull requests and explicit manual dispatch,
not on a merge/push data trigger. Its only permission is `contents: read`; checkout
does not persist credentials. All four actions are pinned to verified commit SHAs.
It installs locked dependencies, lints and runs offline tests, parses dbt without
credentials, validates all three Terraform roots with their backends disabled,
and tests allowlisted containers without runtime network access.

The workflow has no AWS/Snowflake secret reference, OIDC permission, ECR push,
Terraform apply, ECS launch or Step Functions start. Package/provider/image build
downloads are distinct from network-disabled test execution. Opt-in live tests are
skipped unless separately and explicitly enabled outside ordinary PR validation.

Local checks are not a GitHub run. Record the actual run URL, result, artifact usage
and observed no-data-start effects after publication is authorized.

## Immutable promotion review

Terraform `infra/jobs/` is the only task/workflow registrar. `release_plan.py` and
`infra/jobs/review_release.py` reject extra resources, deletes/replacements of the
workflow, role changes, mutable/untested images, secret/command/environment/mount/
logging changes and removal of old-revision retention. A receipt hash-binds the
saved binary, image evidence, template, main configuration and reviewer/generator
source. Verify it again immediately before applying the same binary.

Image evidence must record the processing contract **measured inside the exact
built image**, container test outcome and completed scan findings. Never copy the
prior release's contract hash forward merely because the business SQL is unchanged.
Scan COMPLETE means the scan finished; it does not mean the image is vulnerability-free.

An ordinary release may register a new image/task/workflow revision but cannot alter
platform IAM/network/secrets or start data. Defer while an authorized refresh is
observably active. This is single-operator coordination, not an atomic cross-system
mutex. Recorded immutable versions and retained dependencies protect an overlap.

## Pending protected OIDC path

Before enabling trusted promotion, independently verify:

1. The actual repository visibility, owner/repository, default branch and supported
   protection/environment controls without a paid upgrade or public workaround.
2. Enforced trusted-branch/event review and exact OIDC repository/subject/audience.
   Untrusted PR code must never run with deployment credentials.
3. A distinct release identity limited to the exact application state/lock, ECR
   repository, task families and workflow; exact service-constrained PassRole.
   It must have no direct `ecs:RunTask` or `states:StartExecution` permission and no
   Snowflake/workload-secret/platform-administration access.
4. Actual allowed trusted promotion and denied untrusted/PR/direct-launch cases;
   retained-version rollback and partial-apply inventory; no automatic data run.

No role/trust grant or environment protection is claimed deployed by this runbook.

## Rollback is code rollback, not data rollback

Keep every image/task/workflow version referenced by an execution or the rollback
inventory. A subsequent explicit refresh starts an exact workflow version; running
executions retain their recorded dependencies. Re-promote a previously qualified
digest/contract through the same reviewed Terraform path when needed. Never retag
`latest`, mask drift, mutate old frozen releases or assume a failed apply rolled
back automatically.

Qualified original workflow version 1 remains a retained partial tracer. Version 2
was never data-qualified and has a known stale processing-hash binding; it is not
a valid rollback candidate. Later qualification outcomes belong in
[cloud status](cloud-jobs.md), not inferred from successful registration.

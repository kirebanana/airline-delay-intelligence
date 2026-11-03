# Code delivery and data execution

**Status: actual GitHub validation, protected OIDC, retained-version overlap,
rollback and partial-apply recovery exercised, 2026-11-03.** On that date the owner confirmed that
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

Actual credential-free runs
[41633524681](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41633524681)
and [41634871627](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41634871627)
passed. Protected PRs 1–3 also passed their required validation checks before merge.
These use standard public runners; no paid runner/plan upgrade or raw state/plan
artifact upload is configured. Action pins currently emit a Node-20 deprecation
warning; GitHub executes them under Node 24, and the recorded runs passed.

## Immutable promotion review

Terraform `infra/jobs/` is the only task/workflow registrar. `release_plan.py` and
`infra/jobs/review_release.py` reject extra resources, deletes/replacements of the
workflow, role changes, mutable/untested images, secret/command/environment/mount/
logging changes and removal of old-revision retention. A receipt hash-binds the
saved binary, image evidence, template, main configuration and reviewer/generator
source. Verify it again immediately before applying the same binary.

The guard also compares known planned graphs with the qualified generator. When
new task ARNs make the graph unknown, it verifies exact task/variable references,
the complete archived/current Terraform file inventory and the pinned entire
registrar source. Extra override files/modules, altered archived configuration and
image/processing-contract mismatches are rejected; the checked template must still
match the generator. This closes a review-discovered preexisting template-bypass gap.

Image evidence must record the processing contract **measured inside the exact
built image**, container test outcome and completed scan findings. Never copy the
prior release's contract hash forward merely because the business SQL is unchanged.
Scan COMPLETE means the scan finished; it does not mean the image is vulnerability-free.

An ordinary release may register a new image/task/workflow revision but cannot alter
platform IAM/network/secrets or start data. Defer while an authorized refresh is
observably active. This is single-operator coordination, not an atomic cross-system
mutex. Recorded immutable versions and retained dependencies protect an overlap.

Independent review reported no documented coding-standard violations, two
maintainability heuristics (large delivery coordinator and repository-policy tests
in the workload test context), and one substantive saved-graph binding weakness.
The weakness and its override-file variant were fixed with red/green regression
tests and independently re-reviewed. The two refactoring suggestions are deferred;
they are not claimed as security fixes or accepted specification exceptions.

## Protected OIDC path

The platform root owns one GitHub OIDC provider, `airline-github-release` and its
inline policy; the application root remains the sole task/workflow registrar.
Trust requires audience `sts.amazonaws.com` and the exact immutable subject:

```text
repo:kirebanana@173084883/airline-delay-intelligence@1433493412:environment:release
```

This repository uses GitHub's post-July-2026 immutable owner/repository IDs. The
initial legacy-format subject was denied before obtaining credentials; the corrected
exact subject passed. Never solve a subject mismatch by accepting a wildcard.

Main requires a PR, the GitHub Actions `validate` check and an up-to-date branch;
force pushes/deletions are disabled and administrators are included. The `release`
environment allows only the main **branch**, not matching tags; admin bypass is off.
This solo-owner configuration does not claim independent human reviewer approval.

The release role has only the jobs state/lock, project ECR, three task families,
one workflow and exact service-constrained PassRole permissions. AWS requires
`Resource: *` for the Ohio-constrained `DescribeTaskDefinition` read and definition
validation API; these are not wildcard mutation grants. It can observe admission
on the exact cluster/workflow, but cannot read workload secrets, modify IAM/platform
state, assume another role or directly start data tasks/executions.

Actual qualification:

- [Untrusted signed subject](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41643488916)
  received STS AccessDenied after the immutable trust correction.
- [Signed pull-request subject](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41660920649)
  also received actual STS AccessDenied. This auxiliary same-repository PR check can
  request a GitHub identity token but never exports AWS credentials or uses the
  release environment; fork PRs skip it. Ordinary validation remains credential-free.
- [Non-main environment](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41642439709)
  was rejected by branch protection with no runner or job steps started.
- [Protected dry run](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41645026103)
  authenticated, tested/scanned the exact image, reviewed its plan and proved actual
  `ecs:RunTask` and `states:StartExecution` AccessDeniedException responses.
- [Attended partial-apply recovery and code rollback](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41650132440)
  used protected OIDC to finish the retained qualified image at task/workflow 5.

Ordinary code promotion does not start a refresh. Explicit data requests remain
operator-owned and pin the exact workflow version. Observed-idle checks are not a
cross-system mutex; retained dependencies protect the separately qualified overlap.

Approved main code merges now trigger the same tested/scanned/guarded promotion;
docs-only merges, PRs and schedules do not deploy. The first such promotion passed
in [41658310011](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41658310011),
producing task/workflow 6. Every promotion checks observed-idle admission before
work and again before apply; an active/unknown inventory refuses deployment rather
than resetting, stopping or taking over a refresh.

The final strengthened-guard merge promotion
[41660763998](https://github.com/kirebanana/airline-delay-intelligence/actions/runs/41660763998)
passed with 136 container tests discovered (105 passed, 31 opt-in live skips), the
measured image contract and a completed scan retaining known findings. It promoted
task/workflow 7; a separately explicit isolated replay then succeeded with one
admission task and 28 terminal queries, returning the same committed descriptor.
Independent execution inventory confirmed no merge/promotion data starts before
that deliberate replay. See the [sanitized delivery summary](evidence/delivery-qualification.json).

## Partial apply is not an automatic rollback

The first GitHub rollback registered task revisions 5, then failed because the
provider also needs the non-executing `ValidateStateMachineDefinition` API. Workflow
4 and all task versions 3/4/5 remained intact, with no running tasks/new executions.

Inventory actual resources and protected state before another plan. The normal
guard refuses deposed state. An explicit `recover_partial_apply` dispatch may admit
at most three exact deposed task bindings only when their prior `skip_destroy` is
true; the pinned provider then forgets those bindings **without deregistering AWS
task definitions**. Workflow replacements, foreign families, removed retention and
remote deletions remain rejected. Re-test the exact image and review/hash-verify a
fresh saved plan. Do not edit state, force-unlock a live owner, suppress drift or
pretend the original failed apply rolled back. No automatic recovery is configured.

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

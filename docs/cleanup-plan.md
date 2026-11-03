# Proposed lifecycle and cleanup plan — no deletion authorized

**Status: proposal only, 2026-11-03.** Prepare evidence now; retain infrastructure,
accepted source data, warehouse data and releases until the owner approves exact
actions. Trial or credit expiry is not evidence that resources were deleted.

| Resource / owner | Retain now | Proposed action requiring approval |
| --- | --- | --- |
| Accepted S3 originals/prepared/manifests | All referenced immutable source and weather versions | Inventory dependencies and evidence first; propose exact object/version selectors, never a bucket-wide delete |
| Production RAW and accepted weather input | All accepted input identities | Retain for reproducibility; any removal needs explicit table-level approval |
| Production active/previous releases | Protect both and the minimum 24-hour retired-reader window | Verify pins/readers and preserve summaries before proposing exact retired releases |
| Isolated test candidates/releases/control runs | Preserve qualification and recovery evidence | Enumerate exact test targets/schemas; prove terminal tasks/queries/transactions before any cleanup |
| ECS tasks / Step Functions | No services or recurring refreshes are intended | Verify actual known tasks/executions terminal; stop only explicitly authorized bounded work; never equate STOPPED with SQL termination |
| ECR images / task definitions / workflow versions | Retain every referenced or rollback dependency | Remove only an approved unreferenced version inventory, after execution/reference checks |
| Terraform state and lock objects | Keep protected versioned platform/application state and recovery inventory | Never delete a live lock or state as generic cleanup; require exact owner-led state lifecycle plan |
| Snowflake static objects and resource monitor | Preserve protection and Terraform ownership | No DROP/destroy, quota increase, prevent_destroy removal or workload-admin fallback |
| Secrets and key pairs | Retain scoped existing identities while work/presentation needs them | Owner-approved credential retirement separately; no secret exports or permanent AWS keys |
| Logs and query journals | Preserve sanitized evidence and current configured retention | Export approved sanitized summaries first; retention changes need explicit review |
| VPC/subnet/endpoint/ECR/secrets/log storage | Retain while project remains demonstrable | Review exact Terraform destroy plan only after evidence/dependency checks and owner authorization |
| GitHub workflows and repository | Preserve reviewed code/evidence; prevent unattended data starts | Disable promotion only if requested; visibility/protection/credential changes are separate decisions |

## Before approving any destructive action

1. Record exact account, region, target, resource identifiers, owners and selectors.
2. Check current workflows/tasks, pinned dependencies, SQL sessions/transactions and
   active/previous/retired-reader releases. Unknown work blocks deletion.
3. Preserve sanitized acceptance evidence and the last usable deployment inventory.
4. Estimate retained charges and any export/transfer/delete/recovery exposure;
   identify the owner of continuing AWS, Snowflake and GitHub costs.
5. Review the exact action/plan and recovery limitations. Do not replace it with a
   regenerated broader plan after approval.
6. Execute only approved selectors; independently verify retained/unrelated resources
   afterward, and report any remaining resources and charges.

No infrastructure, data, release, image, state, secret or credential has been deleted
under this plan. Finite job completion and ordinary warehouse auto-suspend are not
cleanup completion. The resource inventory must be refreshed at the eventual
approval time; this proposal intentionally does not freeze stale deletion selectors.

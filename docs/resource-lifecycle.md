# Resource lifecycle and runtime availability

**Observed 2026-11-14.** The owner approved removal of project cloud resources and
data. GitHub/source, local files, human/operator access, unrelated resources and the
account-level budget safeguard are explicitly preserved. This is a resource-status
record, not a claim of acceptance, a zero bill or permanent erasure of provider
recovery/history data.

## Removed or stopped

| Resource | Verified action / disposition |
| --- | --- |
| Local Streamlit and diagram HTTP servers | Both stopped; ports 8501 and 8502 no longer listening. |
| GitHub AWS-dependent workflows | `release.yml` and the two environment/OIDC qualification workflows disabled; credential-free validation remains available. |
| Step Functions | Project refresh, connectivity and retry-qualification state machines deleted after checking for no running executions. |
| ECS | No running/pending tasks or services; cluster deleted. All 36 project task-definition revisions removed; follow-up ACTIVE and INACTIVE inventories are empty. |
| ECR | Project repository and its 13 retained images deleted. |
| S3 data bucket | All 5,406 object/version selectors removed, empty inventory checked, then project data bucket deleted. |
| Networking | Project subnet, explicit route association/table, no-inbound security group and internet gateway removed. |
| IAM | Nine project workload/workflow/release/storage roles and their inline policies removed. |
| GitHub OIDC provider | Deleted only after verifying no remaining role trusts it. Human/operator access preserved. |

## Remaining resources and blockers

| Resource | Current disposition / next action |
| --- | --- |
| `AIRLINE_DB` and all contained source, candidate, release and control objects | Retained. Database is `ACCOUNTADMIN`-owned; approved deletion needs an existing authorized human owner. |
| `AIRLINE_DEV_WH` | Suspended, zero running/queued statements at inventory; owner deletion pending. |
| `AIRLINE_BTS_S3` integration and three Snowflake service users/roles | Owner retirement pending. No administrative authentication fallback or new grants attempted. |
| Secrets `airline-delay-intelligence/snowflake/warehouse` and `/publisher` | `DeleteSecret` denied to the project role; still present, not scheduled for deletion. No secret values exported. |
| CloudWatch `/airline-delay-intelligence/jobs` | `DeleteLogGroup` denied; group remains with 30-day event retention. Retention does not delete the group itself. |
| S3 gateway endpoint and project VPC | `DeleteVpcEndpoints` denied; VPC deletion blocked by the remaining endpoint. No subnet, internet gateway or task ENI remains in that VPC. |
| Versioned Terraform state bucket | Intentionally retained until remaining dependencies are removed. Current three state snapshots backed up outside Git with directory mode 0700 and file mode 0600. No active lock was observed. All historical versions require deletion at the final owner-led step. |
| Preserved account safeguard | `AIRLINE_BUDGET` and its account attachment are not to be removed. Inventory showed 9.84 used /0.16 remaining of 10 credits; lagged/shared observation, not final billing. No data queries/builds were run during teardown. |

Access to broad tag/EventBridge inventory and instance-profile listing was denied.
Project IAM roles were subsequently deleted using their exact identities; IAM
dependency checks succeeded without modifying instance profiles. Do not interpret
this project-scoped Ohio inventory as proof that unrelated regions/accounts contain
no chargeable resources.

## Dependency order for remaining owner actions

1. Keep automatic deployment disabled. Do not run the retained application-release
   workflow or apply old Terraform configuration against the partially removed stack.
2. Using existing human Snowflake authority, confirm account and terminal queries/
   transactions, then remove the approved database, integration and warehouse.
   Retire only the three project service users/roles, preserving the human login,
   operator identity and account budget safeguard. Snowflake Time Travel/Fail-safe
   can retain dropped data and incur storage charges for its configured lifecycle.
3. Using existing AWS owner authority, delete the two exact secrets (a recovery
   window means scheduled rather than immediate deletion), the project log group,
   the remaining S3 endpoint and then its VPC. Preserve the default/shared network.
4. Reconcile the residual inventory against the protected state backups. The remote
   state still describes objects already removed via approved API calls; it is not
   a clean current Terraform plan or a restoration instruction.
5. Delete all object versions/delete markers and the exact state bucket only after
   the remaining-resource reconciliation. Preserve local protected backups; never
   publish raw state, keys, signed URLs or binary plans.
6. Independently verify the exact resource selectors and document any pending
   deletion windows, retained storage and owner-only blockers. Storage/secrets/logs
   can remain chargeable until removed; zero running compute is not zero cost.

The dated [cleanup proposal](cleanup-plan.md) records the earlier preservation
policy. The November 14 approval and actions above supersede its “no deletion
authorized/performed” statements for this explicitly approved scope only.

# Protected static-state migration

**Status: AWS platform/application and Snowflake static state are remote; deferred
Snowflake user/account-monitor adoption is not complete. Verified 2026-11-03.**

| Root | Exact S3 key | Ownership |
| --- | --- | --- |
| `infra/ingestion/` | `aws/ingestion.tfstate` | AWS platform, roles/network/storage/qualification definitions |
| `infra/jobs/` | `aws/jobs.tfstate` | Immutable application task/workflow revisions only |
| `infra/snowflake/` | `snowflake/static.tfstate` | The 12 imported agreed static objects; no runtime data/control ownership |

All keys use the existing protected state bucket in the approved AWS account and
Ohio region, native S3 lockfiles, AES256 encryption and versioning. Backends bind
the permitted account explicitly. Workload-role state denial remains intact;
backend migration did not grant a workload infrastructure permissions.

## Snowflake migration evidence

The destination was independently confirmed absent before migration. Existing
operator permissions already covered exactly the Snowflake state and lock keys;
no IAM expansion was needed. The protected local source snapshot contained nine
resource blocks / 12 instances and no private-key/password/AWS-key patterns in
resource state. Authentication variables remain sensitive/ephemeral, not values
in state or saved plans.

Reviewed backend initialization copied the local state only; it did not log into
Snowflake or create/modify a database, warehouse, role, user, integration or monitor.
All resource and output content compared exactly after migration. Terraform
established a new remote lineage while keeping serial 1; a byte-identical full JSON
state is therefore **not** claimed. Local snapshots/backups were preserved outside
Git. Independent S3 metadata verified the new 61,627-byte encrypted version and no
remaining migration lock.

State/backup content, binary plans and backend authentication configuration remain
outside Git. Do not reset lineage, force-push older state, delete a possibly live
lock or use an administrator workload fallback to obtain a green plan. Any future
state/adoption mutation still needs the matching scoped plan and preserved inventory.

This removes only the remote-state prerequisite. Service-user TYPE metadata and
the account resource-monitor attachment still require an explicitly approved
infrastructure identity and reviewed no-change import/adoption, as described in
[the adoption history](terraform-adoption.md).

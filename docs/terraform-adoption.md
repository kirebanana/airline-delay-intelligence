# Terraform adoption and finite-job preparation

**Status: preparation only, 2026-11-01.** Owner approved provider installation,
inventory and saved-plan preparation. No apply, authoritative import, backend
migration, IAM change or authentication change has been performed. Ticket15 is
not complete until its adoption, backend and live security gates pass.

## Ownership and preservation

| Root | Intended ownership | Current state |
| --- | --- | --- |
| `infra/ingestion/` | Existing S3/reader trust plus proposed minimal AWS job primitives | Existing local bootstrap state; seven live ingestion resources unchanged |
| `infra/snowflake/` | Agreed static database/schemas, roles, warehouse, monitor, integration, format/stage | Twelve exact import-only previews; no authoritative state yet |
| SQL migrations | Publication control tables/procedures and singleton initialization | Not Terraform-managed |
| Runtime pipeline | RAW tables, candidates, release schemas, data and registry DML | Not Terraform-managed |

No resource is imported into both roots. Keep the current source bucket, external
stage trust, service authentication and released data intact. `prevent_destroy`
is retained on adopted Snowflake objects and protected storage. Never remove it
to satisfy a replacement plan. It is a Terraform guard, not an AWS/Snowflake
permission boundary or a substitute for backups.

Provider pins: Terraform1.13.4, AWS6.33.0, Snowflake2.21.0 with committed dependency
lockfiles. The installed Snowflake provider is publisher-signed; import planning
uses existing builder/publisher credentials only. Private keys/passphrases enter
ephemeral sensitive provider variables in process memory, not HCL, plan/state,
command arguments or local scratch artifacts. No administrator fallback exists.

## Import findings

The final saved preview imports twelve objects with **zero create/update/delete**:
the database, RAW/INGEST_TEST/CONTROL schemas, three roles, warehouse, resource
monitor, storage integration, file format and external stage. Import is a state
binding, not a transfer of resource ownership or new ALTER permission. A clean
preview does not prove the current identities can administer ACCOUNTADMIN-owned
objects later.

Service-user adoption and account-level monitor attachment remain explicitly
deferred in non-executable `.tf.example` files:

- Snowflake `SHOW USERS` hides TYPE and other fields without appropriate ownership
  or administrative visibility; `DESC USER` confirms existing SERVICE users. The
  provider read interprets the hidden type as external drift and proposes replacing
  the users. `prevent_destroy` blocked the attempt. Do not suppress `user_type`,
  replace users or give workload roles MANAGE GRANTS to force a green plan.
- The existing monitor is visibly ACCOUNT-level, but the provider's account
  attachment read returns null under the current service identity and proposes an
  account ALTER. That is not an import-only action. Its adoption requires a separate
  owner-authorized infrastructure identity and exact authentication/privilege review.
- The owner increased AIRLINE_BUDGET to10credits; inventory verified10.00quota,
 4.50used/5.50remaining, MONTHLY/ACCOUNT, notify50% and immediate suspension100%.
  Terraform does not reset usage or attach the monitor to the warehouse.

The newer CSV-specific resource produced default/escape changes during import.
The pinned provider's older `snowflake_file_format` resource produces the exact
no-change binding and preserves loading behavior. It is deprecated/preview and
cannot be silently upgraded: a later migration needs its own clean plan. The S3
stage manages private-connectivity choice through its integration, not two
conflicting fields. Inherited retention/concurrency values remain inherited;
import planning does not turn defaults into unnecessary explicit ALTERs.

## Minimal AWS preview

The saved preview contains29additions, zero updates/deletes/replacements and all
seven existing resources unchanged. See [the exact resource-action policy](../infra/plan-policy.json).
It prepares:

- One private, versioned SSE-S3 state bucket and scoped operator state/lock policy.
- One dedicated Ohio VPC/subnet, gateway, routing, no-inbound job security group,
  outbound TCP443and80, and an S3 gateway endpoint.
- One private immutable ECR repository;30-day CloudWatch job logs.
- Two Secrets Manager **metadata** objects without secret values.
- Separate acquisition/warehouse/publisher task roles and an execution role. The
  execution role pulls only the project image and writes job logs, not credentials.
  Each Snowflake workload reads only its own proposed secret. Workload S3 outputs
  require encrypted conditional puts; no object delete or Terraform state access.

There are no ECS services/tasks, executions, schedules, Step Functions workflows,
CI/OIDC trust, NAT, load balancer, listener, SSH or ECS Exec in this preview.
Later ECS tasks explicitly request a temporary public IP; the subnet does not
assign IPs by default. Outbound80supports certificate OCSP/CRL checks, not payload
HTTP. A port rule cannot enforce that intent or a domain allowlist: these jobs
retain outbound/exfiltration risk. No private-only networking is claimed.

The S3 endpoint allows project workload access plus GET of Ohio ECR's
`prod-us-east-2-starport-layer-bucket/*`, needed for signed image-layer downloads.
An endpoint limited only to the project bucket would break image pulls. It does
not grant arbitrary read of unrelated S3 buckets.

## State migration gate

`backend.hcl.example` specifies the intended exact account, Ohio bucket/key,
SSE-S3 and native `.tflock` locking. It is not an active backend. After an approved
bucket apply, take protected owner-only local state backups, review migration
inputs, then migrate the existing state rather than reimporting/recreating AWS
resources. Snowflake static state uses a distinct key in the same bucket. Never
delete state object versions; operator delete permission is for exact lockfiles.

The proposed inline policy does not remove other existing operator privileges
or guarantee other-target denial. Actual combined policies and post-apply
positive/negative locking/access tests remain required. IAM simulation and ECR
registry-scanning configuration reads were denied, so neither apply permission
nor the account's scanning billing mode is claimed verified. No grant expansion
or administrator substitution was attempted.

## Verification and remaining gates

Five mock Terraform tests verify the existing storage controls, state isolation,
networking, trust and credential separation without provisioning anything. The
Python saved-plan guard rejects updates, replacements, unexpected/missing/duplicate
resources, wrong import IDs and unreviewed data reads. Its successful result is
review evidence, **never apply authorization**. Saved binaries require owner review
and hash verification; regenerate and re-review if configuration or live state
changes before execution.

Budget planning remains up to$5/month for small state/ECR/log/two-secret retention,
not a verified bill cap. New-service credit eligibility, ECR scanning mode and
retention/usage assumptions must be confirmed before apply. Future finite
Fargate/public-IPv4/workflow runs require a separate measured envelope. No
infrastructure apply or authentication change is authorized by this document.

Sources: [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3),
[ephemeral variables](https://developer.hashicorp.com/terraform/language/block/variable#ephemeral),
[Snowflake SHOW USERS visibility](https://docs.snowflake.com/en/sql-reference/sql/show-users#access-control-requirements),
[Snowflake connectivity](https://docs.snowflake.com/en/user-guide/client-connectivity-troubleshooting/common-issues),
[ECR S3 layer access](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html).

# Terraform adoption and finite-job preparation

**Status: reviewed AWS platform apply complete, 2026-11-02.** The12Snowflake
imports completed with no resource changes and a clean subsequent plan. After
the initial AWS partial apply, the owner attached the exact state policy, which
was imported without modifying the role. The owner then approved the exact
eight-addition completion binary; it applied8adds/0changes/0deletes. Both original
and completion plan hashes/actions were checked immediately before use.
AWS now has36managed instances and a clean no-change subsequent plan; prior28IDs
and original ingestion bucket/policies/trust are preserved. No backend migration
or authentication change has run. Deferred user/account-attachment adoption and
backend/live access gates mean the whole ticket15is not yet complete.

## Ownership and preservation

| Root | Intended ownership | Current state |
| --- | --- | --- |
| `infra/ingestion/` | Existing S3/reader trust plus minimal AWS job primitives | Local state holds36instances, including original7unchanged; post-apply plan clean |
| `infra/snowflake/` | Agreed static database/schemas, roles, warehouse, monitor, integration, format/stage | Twelve existing objects imported into protected local state; follow-up plan clean |
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

## Verified funding and apply outcomes —2026-11-02

The owner enabled read-only `billing:GetCredits` with `Resource="*"` and activated
IAM Billing access. Actual API results verify four enabled account-local credits,
$156.20remaining, applicable after discounts. All four explicitly include Amazon
Simple Storage Service, Amazon EC2 Container Registry (ECR), Amazon Inspector,
AWS Secrets Manager, AmazonCloudWatch, Amazon Virtual Private Cloud and AWS Data
Transfer. Thus storage/current and noncurrent versions, requests, image storage,
scanning, secret/API usage, logs and chargeable network transfer have corresponding
eligible products, not merely three selected services. EC2/ECS/Step Functions are
also listed, but this does not authorize later runs. Actual expiry is
**2027-06-13**, superseding the earlier owner-attested July date. Taxes and exact
future usage are not a zero-cost guarantee.

The approved AWS preparation plan starts no tasks, images, log producers, public
IPs or NAT/interface endpoints. Empty ECR/state infrastructure introduces no image
scan volume. Conservatively allow$0.80/month for two eventual secrets plus APIs,
usage-based S3/ECR/log storage/requests/transfer within the reviewed small$5/month
envelope; image/job volume must be measured separately before ticket16live runs.

Both exact binary SHA256hashes and action sets were checked immediately before
apply; no regenerated plan was substituted. Snowflake applied12imports/0mutations.
AWS's original29-create apply initially stopped with five direct errors:

- `iam:PutRolePolicy` on the existing operator role is explicitly denied. Preserve
  that self-modification guard; an owner/admin should attach the already reviewed
  exact state/lock policy rather than letting the agent upgrade its own role.
- Missing `ec2:CreateVpcEndpoint` for the approved project S3 gateway endpoint.
- Missing `logs:CreateLogGroup` for the exact job log group.
- Missing `secretsmanager:CreateSecret` for each of the two metadata-only secrets.

Four job/execution inline policies were also uncreated because their failed
dependencies prevented evaluation. No broad fallback, rollback/deletion or new
authentication was attempted. Subsequent Terraform refresh reports no drift among
the27existing instances; all9remaining changes are uncreated parts of the original
scope. A successful plan is not proof of create/tag/retention permission.

Independent AWS reads verify state bucket Ohio/private/versioned/AES256, job
security-group ingress empty, only TCP80/443egress, expected subnet/routes, and an
empty ECR repository. Registry scanning configuration remains unreadable. There
are no running job resources; no secret values exist from this apply. Local state
backups and diagnostics are preserved; the owner subsequently approved the exact
completion plan below, not reuse of the stale original plan.

### Completion apply and independent inspection

Owner-approved completion binary SHA256:
`f8c4eeccd5ceccecf050ca6220c9c87f321ef9a5dc43d47ef97c16b3a4efd9d3`.
The guard verified8creates/28unchanged/0updates/0deletes, then applied that binary
without replan/substitution. A subsequent36-resource plan is all no-op.

Independent AWS MCP reads verified the available S3 gateway endpoint and exact
route association/policy,30-day empty log group, two tagged secret containers
with no versions, four ECS trust policies and all four scoped inline policies.
Warehouse and publisher secret permissions reference their own exact generated
ARNs; acquisition/execution have no secret permission. Original operator
`ProtectAgentRole` explicit deny remains in place, including PutRolePolicy,
DeleteRolePolicy, trust changes and PassRole on the operator itself. No attached
managed policies or administrator fallback were added by the agent.

Remaining work is not hidden by the clean infrastructure plan: state is still
local; backend migration/locking tests and deferred Snowflake identity adoption
need their existing authorization gates. Ticket16can progress locally, but ECR
registry-scanning inspection still fails `ecr:GetRegistryScanningConfiguration`.
No image push or substantive ECS workload proceeds before scanning-cost review
and bounded S3/ECR/Snowflake/endpoint connectivity tests. No secret values or
new authentication were installed by completing this plan.

Sources: [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3),
[ephemeral variables](https://developer.hashicorp.com/terraform/language/block/variable#ephemeral),
[Snowflake SHOW USERS visibility](https://docs.snowflake.com/en/sql-reference/sql/show-users#access-control-requirements),
[Snowflake connectivity](https://docs.snowflake.com/en/user-guide/client-connectivity-troubleshooting/common-issues),
[ECR S3 layer access](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html).

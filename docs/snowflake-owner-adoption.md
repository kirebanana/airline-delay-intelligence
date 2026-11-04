# Owner-controlled adoption of the three existing SERVICE users

**Status: three-user adoption completed, 2026-11-04; official-provider normal plan
clean. Literal no-difference refresh-only acceptance remains unmet solely because
authentication advances read-only last-login timestamps.** Scope is
exactly `AIRLINE_DEV`, `AIRLINE_PUBLISHER`, `AIRLINE_READER`, plus read-only verification
of the existing account monitor. No user/grant/key/default/authentication-policy changes.

## Completed outcome: no further owner commands

Approved plan: `~/.local/state/airline-user-adoption-bootstrap-20261104T135154Z/users.tfplan`.
SHA-256: `684434be40060d3806a7494365438ed1a889b66ea488ac64f53f1b7bf1df4626`.
The approved saved plan contained exactly three imports, fifteen no-op managed
instances and zero creates/updates/replacements/deletes. The owner-local exact apply
exited **0**. The unchanged official provider then produced a normal plan with
**exit 0, fifteen instances, zero imports and zero remote changes**. Before/after
defaults, SERVICE types, both public-key fingerprints, grants and user parameters
match. The account monitor remains ACCOUNT / 10.00 / MONTHLY / immediate 100%.

An independent protected-backend read confirms all fifteen bindings and the three
provider-internal timer defaults. AWS metadata confirms versioned AES256 state,
version `X5UDe77LvZDk4uT1Wzo0moXd0O59xDBG`, and no residual Snowflake state lock.
No state was manually edited. The bootstrap override was process-scoped and removed;
the official provider installation and lock file were not replaced.

**Do not rerun the owner-plan or owner-apply scripts.** No further password entry,
bootstrap SQL, data workflow, image promotion or cleanup is needed for this closure.
The guarded launchers and exact source patch remain as reproducibility/audit evidence,
not a permanent custom-provider dependency. The password was supplied only in the
owner's terminal, used ephemerally, and not retained by the agent or written to files.

### Refresh-only exception (not waived)

The official-provider refresh-only plan completed successfully but returned detailed
exit **2**. Its only resource differences are
`snowflake_service_user.{builder,publisher,reader}.show_output[0].last_success_login`.
Authenticating the existing workload providers/read-only snapshot connections advances
these observations. There are **no resource actions, output changes, key/default/type/
grant/parameter changes, or account-monitor configuration changes**. Serialized-state
differences are those three observations, serial/lineage and cleared successful variable
check records. This is not a failed import, a requested user alteration or a reason to
apply the refresh plan.

The literal no-difference/exit-zero refresh-only requirement is **not met**. It remains
an explicitly disclosed owner-acceptance item; do not mark full infrastructure acceptance
complete, hide the metadata with broad ignores, keep a custom plugin active, or request
more password reruns merely to chase moving login timestamps.

[Sanitized final evidence](evidence/snowflake-importer-bootstrap.json) records exact
outcomes and limits. Raw plans/state and before/after snapshots remain protected outside
Git. The preparation sections below are historical/reproducibility reference, not steps
to repeat. Future complete-root maintenance uses the official provider and the existing
owner-controlled authentication boundary, never an administrative workload fallback.

## 1. Owner SQL: inspect, do not grant

Sign in to the existing account as your **human owner**. In a Snowsight SQL worksheet:

```sql
USE ROLE ACCOUNTADMIN;
USE SECONDARY ROLES NONE;
SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME(), CURRENT_ACCOUNT(),
       CURRENT_REGION(), CURRENT_USER(), CURRENT_ROLE();

SHOW USERS LIKE 'AIRLINE_DEV';
SHOW USERS LIKE 'AIRLINE_PUBLISHER';
SHOW USERS LIKE 'AIRLINE_READER';
SHOW PARAMETERS IN USER AIRLINE_DEV;
SHOW PARAMETERS IN USER AIRLINE_PUBLISHER;
SHOW PARAMETERS IN USER AIRLINE_READER;
SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET';
```

Require `LMOOEWP / DQ15927 / DC50202 / AWS_US_EAST_2`, your human login, three exact
unredacted `TYPE=SERVICE` rows, and monitor `LEVEL=ACCOUNT`. Run the supplied
[`owner-preflight.sql`](../infra/snowflake/owner-preflight.sql) to also capture exact
defaults, existing key fingerprints and grants for before/after comparison. Its
`USE ROLE` commands change only this session, not user defaults or role assignments.

**No bootstrap GRANT, CREATE USER, ownership transfer or ALTER USER is needed** if
your existing owner role already passes these reads. Do not elevate workloads.
If these checks fail, stop and report only which read failed—not credentials.

## 2. Owner-local Terraform authentication

Use the distinct profile `[airline_identity_owner]` in **`~/.snowflake/config`**,
outside both repositories, mode `0600`. This is the Terraform provider's file,
**not** Snowflake CLI's `config.toml`. Add a section; do not replace existing sections.

For the owner's existing username/password-only login, the section contains only:

```toml
[airline_identity_owner]
organization_name = "LMOOEWP"
account_name = "DQ15927"
user = "YOUR_EXISTING_HUMAN_OWNER_LOGIN"
role = "ACCOUNTADMIN"
authenticator = "SNOWFLAKE"
```

If the existing login requires MFA, use `USERNAMEPASSWORDMFA` instead. Do not add,
disable or change MFA/authentication policies for this procedure. If Snowflake
rejects password-only programmatic authentication, stop and report the sanitized
error; browser login behavior does not guarantee provider authentication succeeds.

The owner-run command accepts the **existing** password only in that local
terminal. It remains an ephemeral process input—not a chat message, shell command
arguments, Terraform state/plans, Git files or new authentication keys. No password
or token is written to the profile by the wizard. Re-authenticate locally for apply
if necessary; do not disable MFA or enable token caching to make this work.

If an existing owner SAML SSO profile already works, use `EXTERNALBROWSER` instead
and leave password variables unset. Browser SSO requires a configured IdP; merely
being logged into Snowsight is not a Terraform session. Existing owner key/OAuth
profiles may be reused unchanged; do not create a new permanent key or token for
this import. Tell the agent only the authentication **method/readiness**, never its
secrets. An owner profile does not grant ACCOUNTADMIN to anyone.

The owner provider alias applies **only** to these three user resources. Existing
builder/publisher providers remain unchanged. Future complete-root maintenance needs
the same owner-controlled boundary; CI receives no owner credentials.

## 3. Owner-run plan; stop for approval

Use the already initialized workspace, verified Terraform **1.13.4**, existing AWS
profile `airline-old-dev` and project virtual environment. The temporary Go compiler
download/build was separately approved and completed outside the repositories.
No system installation or authentication-policy change is part of this procedure.

From the outer workspace:

```bash
bash project/infra/snowflake/owner-plan.sh
```

The owner has already confirmed the SQL and profile setup; **do not repeat those
steps or the MFA questions**. The only prompt is the existing password, entered
hidden in that local terminal. The command produces and reviews a saved plan, then
**stops** for approval. The old wizard command forwards here to prevent another
unproductive setup loop. The helper refreshes existing public
keys read-only and supplies existing workload keys only to their original ephemeral
provider variables. It never reads/copies the owner's profile or stores credentials.

Evidence is mode-protected under a new `~/.local/state/airline-user-adoption-bootstrap-<time>/`
directory, outside Git: prior state backup, saved binary plan and reviewed receipt.
The process uses the separately approved **one-time corrected importer**, pinned
to its tested executable digest. The official installation/lock remain unchanged;
the receipt also binds the bootstrap manifest, CLI configuration and actual binary.
[Exact source patch, build provenance, tests and limitations](../infra/snowflake/bootstrap/README.md).
The review requires:

- Exactly three imports at `snowflake_service_user.builder`, `.publisher`, `.reader`,
  IDs `"AIRLINE_DEV"`, `"AIRLINE_PUBLISHER"`, `"AIRLINE_READER"` including quotes.
- All fifteen managed bindings present; the twelve existing ones unchanged.
- **Zero creates, updates, replacements or deletes.** No unreviewed drift, unexpected
  imports, extra configuration/override modules or authentication material.
- Exact binary/configuration/provider-lock/reviewer hashes recorded for rechecking.

Return the sanitized action counts and `plan_sha256` for review. Keep personal
authentication, raw state, binary plan and unsanitized logs out of chat/public Git.
If a public key/default differs, fix the *configuration to match verified reality*,
not the remote identity. Never suppress TYPE drift or remove `prevent_destroy`.

### First-plan correction: preserve transient locks; distinguish refresh metadata

The first owner-run plan proposed updates on all three users solely because provider
2.21.0 imports `mins_to_unlock` as null while its configuration default is the internal
sentinel `-1`. Its source deliberately does not read this continuously changing timer.
The zero-change reviewer correctly refused the plan. Do not apply that saved binary.

A trial narrow `ignore_changes = [mins_to_unlock]` entry removed the displayed timer
difference but **did not make the plan safe**. It is not an approved solution; neither
saved plan may be applied. During these rejected attempts no provider patch, state
editing, user unlock or default change was used against Snowflake. TYPE, keys, defaults, disabled state and
authentication policies have not been ignored. [Pinned provider source](https://github.com/snowflakedb/terraform-provider-snowflake/blob/v2.21.0/pkg/resources/user.go).

The first plan also refreshed credit consumption, warehouse resume/update timestamps,
and the stage's absent access-point value from null to empty string. The reviewer now
records an exact allowlist of those metadata paths; the access-point exception allows
only that null-to-empty normalization. Any additional drift still fails. All fifteen
planned resource actions must remain `no-op`, irrespective of allowed refresh metadata.
Any successful correction requires a **new** saved plan/hash and owner approval.

The second owner-run plan still reported three updates because the provider marks
read-only `show_output` unknown. An isolated local HTTP fixture replayed the installed
2.21.0 plugin using the saved snapshot, dummy credentials and a separate local backend,
with no Snowflake access. It confirmed that CustomizeDiff still sees null-to-`-1` for
the timer despite `ignore_changes`. A fixture-only apply attempted
`ALTER USER ... UNSET MINS_TO_UNLOCK`; the fixture refused it. **These are not harmless
metadata-only updates.** The zero-update review remains mandatory.

In a diagnostic fixture with the provider's own `-1` default initialized, the same
installed plugin produced `no-op`, even without ignored fields. This identifies the
proposed fix: initialize that sentinel in the provider importer without issuing user
DDL. It is not permission to edit protected state or treat a fixture as a real plan.
The importer patch has now been compiled with the separately approved temporary
compiler. Its regression fails on the original importer and passes with the patch;
the resource-unit suite passes. All three user snapshots passed actual-plugin
import-only local plan/apply tests against a mutation-refusing loopback fixture.
The untouched official plugin then produced normal no-change plans for all three,
without ignored attributes. A second build reproduced the exact binary digest.
The owner first approved plan preparation, then explicitly approved the exact real
saved plan/runtime; that separate approval authorized the completed three imports.
The latest official 2.22.1 importer source also lacks the initialization; upgrading
alone is not an established fix.

The initial local unit tests and Terraform validation alone did not establish live-provider
convergence; the later real outcome is recorded above. Do not ask the owner to repeatedly regenerate plans on that evidence
alone, approve computed-only updates as `no-op`, broaden ignored security fields,
edit saved plans/state, or test an update against the actual account.

## 4. Approved exact apply and clean verification

No apply is authorized by running the command or obtaining a review receipt. After
the owner explicitly approves the **actual saved plan and bootstrap runtime hashes**,
recheck its receipt with `review_user_adoption.py ... --verify --bootstrap-manifest ...`
under the exact bound process-scoped CLI configuration. Apply **that same binary** under
the owner profile with ephemeral workload/password inputs. Do not regenerate a plan and
silently treat it as approved. The guarded launcher implemented this sequence for
the completed import; this historical procedure is not a request to apply a new plan.

Afterward remove only the process-scoped bootstrap override and return to the
unchanged official provider. Require both a normal no-change plan and:

```bash
terraform -chdir=project/infra/snowflake plan -refresh-only -detailed-exitcode \
  -input=false -out=/OWNER_PROTECTED_DIRECTORY/users-refresh.tfplan
```

The original strict gate required exit **0** and no differences. The actual apply
launcher independently inspects refresh-only `prior_state`, actions, drift, outputs
and both serialized snapshots (the format differs from a normal plan). It keeps that
gate pending when exit code is 2. Before/after identity and monitor checks passed;
see the real outcome and exception above. No verification plan was applied.
No state editing, broad admin fallback, ownership transfer or key changes occurred.

**Known verification caveat:** local official-provider refresh-only replay displays
No changes and has no drift/actions; the two serialized resource/output snapshots
match, excluding serial/lineage. Nevertheless Terraform 1.13.4 returns detailed exit
code 2. This is not exit-zero evidence and does not waive the final real-account
refresh acceptance gate. Also, refresh-only JSON may contain resources only in
`prior_state`, not `resource_changes`; the verifier must account for that actual
format before final use. No owner rerun or acceptance claim is justified by unit
tests that contain only synthetic normal-plan JSON.

## Account-monitor attachment

Do not enable `deferred-account.tf.example`. Provider **2.21.0 does not read the
account resource-monitor attachment**; more privilege does not repair that limitation.
The monitor object itself is already imported. Keep the correct binding unchanged.

```bash
project/.venv/bin/python project/infra/snowflake/verify_monitor.py
```

This uses existing scoped MONITOR access, issues only SHOW, and fails if the exact
account-level protection is missing/invalid. It cannot attach, alter or recreate a
monitor. [Provider limitation and primary sources](snowflake-adoption-gap.md).

## Preparation verification (not adoption completion)

On November 4, Terraform validation and formatting passed (the existing file-format
deprecation warning remains), Ruff passed, twenty-five offline review/monitor/runtime/apply tests passed,
and `bash -n` passed. Shellcheck was unavailable; it was not installed. The separately
approved Go compiler remained isolated under `/tmp/opencode`. The live
read-only monitor check returned `ACCOUNT`, `10.00`, `MONTHLY`, `100%`. Existing
workload self-DESC reads confirmed all three SERVICE types and captured existing
defaults/key fingerprints; they do not substitute for owner-visible provider reads.

A fresh mirror of the **public** project repository, including advertised branch
and PR refs, was audited at main `98c94f18fb510b871eff6f278068112c8dcb0d51`:
313 reachable blobs and 166 historical paths, with no credential/private-key/state
pattern findings or tracked state/plan/key file paths. Scoped new/changed adoption
files also had no findings. This is a pattern/path audit, not an exhaustive guarantee
or inspection of unadvertised deleted objects/GitHub caches. Raw plans and state
remain outside Git. [Final image-risk assessment](image-security.md).

Authentication references: [pinned provider configuration](https://github.com/snowflakedb/terraform-provider-snowflake/blob/v2.21.0/docs/index.md),
[pinned authentication guide](https://github.com/snowflakedb/terraform-provider-snowflake/blob/v2.21.0/docs/guides/authentication_methods.md),
and [SHOW USERS privilege/redaction rules](https://docs.snowflake.com/en/sql-reference/sql/show-users).

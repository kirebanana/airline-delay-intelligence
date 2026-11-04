# Snowflake adoption outcome and remaining provider coverage

**Status: all three SERVICE users imported, 2026-11-04; official-provider normal plan
clean at fifteen managed instances. Account-attachment Terraform coverage remains
deferred, and literal no-difference refresh-only verification is an explicit metadata
exception.** Existing authentication, account budget binding and production releases
are preserved. Full acceptance still needs owner review of the disclosed exceptions.

## Exact inventory and disposition

| Terraform address | Existing object | Disposition |
| --- | --- | --- |
| `snowflake_service_user.builder` | `AIRLINE_DEV` | Imported using the explicitly approved no-change plan and human-owner provider boundary. |
| `snowflake_service_user.publisher` | `AIRLINE_PUBLISHER` | Imported; existing keys, defaults, grants and parameters unchanged. |
| `snowflake_service_user.reader` | `AIRLINE_READER` | Imported; same unchanged-identity verification. |
| `snowflake_current_account.budget_attachment` (proposed resource) | Existing account-level binding to `AIRLINE_BUDGET` | **Provider limitation, not just missing privileges:** provider 2.21.0 does not read this attachment into state. |

Fifteen instances, including the monitor object and all three users, are now managed
in the protected backend. The account-attachment example stays inactive. The official
provider is restored; no permanent fork or administrative workload grant was used.
No runtime data objects, accepted facts or frozen releases need privileged import.

The official normal plan exits 0 with no changes. Refresh-only exits 2 solely for
read-only last-login observations on the three users, with zero resource actions.
This is recorded, not suppressed or counted as a literal clean refresh-only result.
[Actual outcome, evidence and reproducible owner boundary](snowflake-owner-adoption.md).

## User metadata boundary

The provider reads `SHOW USERS`, `DESC USER`, and `SHOW PARAMETERS IN USER`.
`SHOW USERS.TYPE` is redacted under current workload roles even when self-description
confirms SERVICE. The pinned provider takes the type from SHOW, so the redaction
causes an unsafe replacement proposal. `prevent_destroy` must remain enabled.

Snowflake documents target-user OWNERSHIP or global MANAGE GRANTS for unredacted
SHOW metadata. Ownership of each exact user is the narrow documented sufficient
authority across the provider's reads; MANAGE GRANTS alone is not a documented
substitute for describing another user. Do not grant global MANAGE GRANTS or
ACCOUNTADMIN to builder, publisher or reader identities. Authentication succeeds
today; the missing authority is metadata/user administration, not a bad key.

## Minimum safe owner-only procedure

The exact SQL, separate owner-profile setup and three-import/zero-change approval
procedure are authoritative in [owner-controlled adoption](snowflake-owner-adoption.md).
Use existing human authority: the current scope does not authorize new grants,
ownership transfers, authentication changes or workload privilege escalation.

## Account-monitor attachment is different

Provider 2.21.0's `ReadCurrentAccount` never maps `resource_monitor` into state; its
documentation explicitly says external changes to this property are not detected.
Even ACCOUNTADMIN cannot make a fresh import faithfully read this field. A same-
value `ALTER ACCOUNT SET RESOURCE_MONITOR` may seed state but is a remote mutation,
not an import-only solution or independent drift detection.

Snowflake requires the owner's ACCOUNTADMIN role for account-level attachment.
MONITOR permits observation and MODIFY permits monitor changes; neither grants
account attachment. **No bootstrap SQL is needed for the already correct binding.**
Leave it unchanged and independently verify `AIRLINE_BUDGET` has LEVEL=ACCOUNT.
Any future provider fix, alternative ownership strategy or documented acceptance
exception needs review. Do not activate the default-builder account example,
suppress attachment drift, edit state to fabricate coverage or give ACCOUNTADMIN
to automation. A broad current-account resource can affect unrelated parameters.

## Sources (checked 2026-11-03)

- [Snowflake SHOW USERS access requirements](https://docs.snowflake.com/en/sql-reference/sql/show-users#access-control-requirements).
- [DESCRIBE USER access requirements](https://docs.snowflake.com/en/sql-reference/sql/desc-user#access-control-requirements).
- [Resource monitor administration](https://docs.snowflake.com/en/user-guide/resource-monitors).
- [Pinned provider user reads](https://github.com/snowflakedb/terraform-provider-snowflake/blob/ba89f50071b3b30bde94dbb83d8eef0b065fb9d5/pkg/resources/user.go).
- [Pinned provider account reads](https://github.com/snowflakedb/terraform-provider-snowflake/blob/ba89f50071b3b30bde94dbb83d8eef0b065fb9d5/pkg/resources/current_account.go).
- [Pinned account resource limitations](https://github.com/snowflakedb/terraform-provider-snowflake/blob/ba89f50071b3b30bde94dbb83d8eef0b065fb9d5/docs/resources/current_account.md).

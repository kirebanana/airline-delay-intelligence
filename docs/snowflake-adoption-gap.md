# Deferred Snowflake adoption and minimum owner procedure

**Status: deferred, 2026-11-03.** Existing objects, authentication, account budget
binding and production releases are preserved. These gaps prevent full managed-
infrastructure acceptance, not unrelated authorized application/delivery testing.

## Exact remaining inventory

| Terraform address | Existing object | Why current authentication is insufficient |
| --- | --- | --- |
| `snowflake_service_user.builder` | `AIRLINE_DEV` | Workload role lacks owner-level metadata visibility for provider reads. |
| `snowflake_service_user.publisher` | `AIRLINE_PUBLISHER` | Same visibility issue. |
| `snowflake_service_user.reader` | `AIRLINE_READER` | Same visibility issue. |
| `snowflake_current_account.budget_attachment` (proposed resource) | Existing account-level binding to `AIRLINE_BUDGET` | **Provider limitation, not just missing privileges:** provider 2.21.0 does not read this attachment into state. |

Twelve static instances, including the monitor object itself, are already imported
and stored in the protected remote backend. The remaining examples are inactive.
No runtime data objects, accepted facts or frozen releases need privileged import.

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

1. Use the owner's existing local authentication and a role that already owns or
   inherits ownership of the three user objects. **Do not send personal credentials,
   tokens, keys, browser sessions or connection configuration to the agent.** No new
   privileges or login are needed if the owner already holds the owning roles.
2. Owner verifies exact SHOW rows expose TYPE=SERVICE and DESC/SHOW PARAMETERS work
   for all three users. Do not assume SECURITYADMIN alone owns every user.
3. Prepare a separate `snowflake.identity_owner` provider alias used only by those
   three resources. Preserve existing public keys, defaults, role assignments and
   user types. Keep workload providers and CI credentials unchanged.
4. Back up protected remote state and obtain its normal lock. Owner runs Terraform
   in their own session. Import IDs are `"AIRLINE_DEV"`, `"AIRLINE_PUBLISHER"` and
   `"AIRLINE_READER"`, including the identifier quotes.
5. Review a saved plan with **exactly three imports and zero remote creates, updates,
   replacements or deletes**. Any type/default/key change stops the procedure.
   Apply only the approved exact plan and verify a subsequent no-change refresh.
6. Return only sanitized action counts, revision/plan hashes and unchanged public-
   key fingerprints. Raw authentication, state and binary plans remain protected.

If no existing owner role can do this, a separate proposal may transfer ownership
of only these three user objects to a dedicated owner-controlled infrastructure
role. User ownership can alter authentication and is **not read-only**; that transfer
is a security change requiring separate approval. It is not necessary for ongoing
delivery. No ownership transfer has been performed.

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

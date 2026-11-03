# Attended cloud recovery

**Status: external-abort, post-commit and dedicated detached-transaction recovery,
next admission, stale fencing and pinned-reader checks exercised.** This is an operator runbook, not
an autonomous recovery service or authority to stop unrelated work.

See the [specification's uncertainty contract](specifications/airline-delay-intelligence.md#d09-bounded-execution-and-ordinary-recovery-not-a-watchdog-platform)
and [local originating-identity recovery](local-recovery.md). Cloud recovery reuses
that SQL/control protocol only after independently proving the cloud producers
terminal.

## Evidence required before clearing admission

1. Preserve the original request, exact input/weather/processing map, cumulative
   ledger snapshot/history hash, workflow version, launch intent/client token and
   actual execution/task identities. Never generate a new request merely because
   a launch response was lost. Exact supported name/input idempotency must resolve
   to the same execution, not a second writer.
2. Collect complete execution history and exact ECS task descriptions. A terminal
   workflow can still have a running task. An unaccounted scheduled launch or
   missing task identity blocks recovery; list absence is not termination evidence.
3. Stop only known authorized producers if necessary, then verify actual STOPPED
   state separately. Preserve durable request-scoped S3 journals, including session
   registrations, pre-query intents, query IDs/results and any incomplete interval.
4. `cloud_recovery.terminal_cloud_scope` checks exact request/target/deployment
   binding and known terminal tasks; it does **not** claim SQL or transactions are
   terminal. Pass that exact originating-session scope to attended recovery.
5. Use each originating builder/publisher identity to terminate its own exact
   session and verify known query statuses. **Always** inspect that user's matching
   transactions, explicitly abort only those IDs if necessary and prove none remain.
   The real probe demonstrated that session termination can leave a transaction
   running. For the qualification, verify the exact uncommitted guard write rolled back.
   No administrative or broad warehouse abort fallback is allowed.
6. Reconcile the exact run/publication before retiring matching authority. A
   published run returns its committed descriptor, not a rollback. A stale recovery
   must never clear a newer request/attempt/fence.
7. Write durable terminal/publication/cleanup proof **before** unblocking the same
   cumulative ledger. Keep elapsed work and reserve; uncertain work is conservatively
   accounted through attended recovery rather than assigned zero cost. Then verify
   active/previous and production descriptors and test a deliberate next admission.

`RECOVERY_REQUIRED`, workflow execution state, publication outcome and cleanup
state are separate facts. Here, cleanup means scoped execution/session/authority
reconciliation—not permission to delete infrastructure, artifacts or data.

## Failure demonstrations

- **Wrong immutable checksum:** must fail before SQL/claim and never produce a
  completed result. A missing result is not success.
- **External workflow abort:** `.sync` cancellation is best effort. The actual
  qualification kept the original claim blocked, verified three stopped tasks,
  then reconciled their three originating sessions before another run.
- **Post-commit result collision:** a create-only isolated report can intentionally
  fail after publication commits. Preserve the committed descriptor and reconcile
  it; never infer data rollback from a failed workflow.
- **Detached transaction probe:** a separately registered finite qualification
  task holds only its exact test-target guard and runs a fixed server-bounded read,
  then intentionally exits without connection cleanup. Its durable session/query
  evidence exists specifically to prove why STOPPED alone is insufficient.

Ordinary refresh never selects the transaction-probe entry point. Its request has
no arbitrary SQL/commands, cannot target production and requires matching fresh
claim authority. The definition adds no service, scheduler, IAM or network change.
Its infrastructure and evidence remain retained under the [cleanup proposal](cleanup-plan.md).

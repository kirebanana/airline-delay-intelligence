# Bounded local execution and attended recovery

The managed `airline refresh` path uses a nonexpiring target claim, decreasing
deadlines and a durable own-work journal. This is not a watchdog, stale-lease
takeover, general SQL canceller or an AWS execution adapter.

## Effective limits

- Whole local refresh: 45 minutes, shared across load/build/publication; a new
  stage does not reset that absolute deadline. A warehouse operation is at most
  45 minutes; every SQL statement is additionally capped at 600 seconds, queue
  wait at 60 and control lock wait at 5, all decreasing with remaining time.
- Publication and attended recovery: at most five minutes each. Connection
  login/network/socket timeouts are clamped to remaining time. Only identified
  pre-return login transport failures may retry once, spending the original
  connection deadline; deterministic errors and workload SQL do not auto-retry.
- dbt has two threads in a separate finite process group. Parent/child use a
  ready/go handshake while holding a shared producer lock. Parent termination
  cannot authorize a late-starting child after recovery. Timeout cleanup permits
  five seconds for TERM and five for KILL. Local exit is **not** SQL termination.
- The existing X-Small warehouse, 60-second auto-suspend and account resource
  monitor remain unchanged. The current owner-authorized continuation ledger has
  no invented elapsed/one-credit batch cap, but preserves measured accounting,
  single-operator locking and a recovery allowance. Old ledgers retain their
  original authorization; never reset them to bypass a stop.

At X-Small's one credit/hour, a 600-second detached SQL ceiling is approximately
0.167 compute credits of warehouse time, not one charge per concurrent query.
Allow additional queue/cleanup/idle/shared-usage uncertainty: the current ledger
keeps 0.5 observed monitor credit for attended recovery. These are conservative
operating estimates, not a hard billing cap; storage and monitor lag remain separate.

## Durable evidence and admission

Each create-only output holds intent, request/attempt/authority identities,
candidate/results or a sanitized failure, and `work.jsonl`. The append-only,
fsynced journal records originating builder/publisher session IDs, submission
intent, statement hashes (not SQL/parameters), query IDs and child lifecycle.
dbt child connections use the same journal and decreasing server limits.

An interrupted active budget entry or unknown error blocks further managed live
work. Target authority remains blocked even after its deadline; absence from a
list, a stopped laptop or a killed child never retires it. Known synchronous
validation failures attempt bounded normal retirement. Unexpected transport,
process, result or commit failures require attended reconciliation.

## Exact attended command

Preserve diagnostics; identify the exact output and its original shared ledger:

```bash
airline recover-local --output /private/exact-attempt \
  --budget-state /private/original-shared-budget.json --funding-verified
```

The command refuses while any registered local producer holds the attempt lock.
It takes the original ledger lock, checks matching work identity, and uses each
originating service user to terminate **only its recorded sessions**. A session
termination acknowledgment is not transaction proof: recovery inspects that user's
transactions for the exact recorded session, aborts only those transaction IDs and
positively verifies none remain. This covers a lost query-ID/transaction-submission
interval without assuming session abort implicitly rolled it back. It also verifies
all retained query IDs have explicit terminal states; unknown, disconnected, unavailable or
unsupported evidence leaves authority/admission blocked. No administrator fallback
or warehouse-wide abort is used.

After terminal-work proof, a fresh publisher locks the target before reading the
exact run. A possibly committed release is reconciled rather than repeated or
rolled back. Otherwise only the matching old request/attempt/fence is retired;
stale recovery cannot clear a newer writer. Proof is preserved before local
admission is restored. Execution, publication and cleanup outcomes are separate.
Interrupted elapsed accounting is conservatively completed, never reset.

A post-publication bookkeeping failure does not mean the data rolled back. A
deliberate next request gets a new request ID after successful attended recovery.
If recovery itself loses acknowledgment, repeat the same attended reconciliation;
never force-load, clear claims by hand or delete diagnostic schemas to unblock it.

## Evidence and limits

Real isolated process-death tests exercise detached bounded SQL, an open inserted
transaction, both retained and lost query IDs, blocked claims, own-user session
termination, actual rollback, stale recovery and successful next-run admission.
Offline tests cover unknown-status refusal, live-producer exclusion, finite child
termination, nested deadline preservation and bounded/deterministic login retries.
Default discovery does not launch those funded tests.

The final three-case real suite passed together on 2026-10-30 (418.50 seconds):
the process-death cases above; actual lost COMMIT response and post-commit result
write failure with exact committed-release recovery; and a server-enforced
two-second statement timeout observed with a longer client allowance. A managed
dbt fixture build also passes with child handshake and shared query journaling.
Review fixes recalculate limits after configuration and carry the fresh limits
with each SQL statement, rather than reusing time already spent configuring it.

The 2026-11-03 cloud client-death qualification exposed why the explicit transaction
step is necessary. Its fixed query continued after ECS STOPPED and was canceled by
the measured 120-second server timeout; an uncommitted test-target guard transaction
still appeared running after session termination. Scoped originating-user transaction
abort proved rollback, preserved both releases and allowed matching authority
retirement. Regression tests now reject foreign-user transaction scope and verify
that only the recorded session's transaction is aborted.

The earlier diagnostic claim without this journal is **not automatically adopted
or cleared**. Legacy standalone loading remains single-writer/attended; managed
refresh is the qualified coordinator. No generalized concurrent RAW-loader claim,
instant orphan detection, autonomous repair, ECS STOPPED/SQL equivalence or AWS
launch/abort qualification is asserted here; the latter remains ticket18.

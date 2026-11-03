# Finite cloud job image

This adapter currently admits **one accepted month and isolated test targets
only**. It is not a replacement for full-baseline/weather acceptance. Source
selection reuses immutable accepted S3 objects; it does not claim to reacquire BTS.

```sh
python containers/jobs/export.py
python containers/jobs/build.py
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 128 --memory 2g \
  --entrypoint python airline-jobs:local -m unittest discover -s tests
```

The build helper copies only allowlisted Python, SQL, dbt YAML/SQL, lock and
requirements files to a temporary context. It excludes data, credentials,
Terraform state/plans and generated dbt artifacts. `/work` is the only declared
writable volume; its image ownership supports UID65532 on Fargate without root
startup or an ingress listener. No runtime dependency installation.

The experimental dbt parser is distributed as a bootstrap sdist that downloads
a platform wheel. The export helper verifies the locked sdist hash, reads its
embedded asset manifest without executing it, and pins the matching upstream
Linux/amd64 wheel URL and SHA256. All installation still requires hashes and
binary distributions. The base-image package update is not a clean-scan guarantee;
retain actual ECR findings and applicability review for each promoted digest.

Workload keys are retrieved in memory from an exact Secrets Manager version by
the originating workload role. dbt's finite child injects only the warehouse
credential at its external connector boundary; no key file or key-bearing CLI
argument/environment variable is created. Connections disable secondary roles
and verify the real account, region, role and user.

Stages use create-only request/mode intent markers and durable query/session
events before SQL. A missing acknowledgement, nonzero exit, deadline or missing
completed report does not authorize another mutation. Claims remain blocked for
attended recovery; no automatic takeover, finalizer or production-target fallback.
The coordinator checks actual `.sync` task/image identity and bounded S3 control
reports separately, then hashes the referenced stage report before using it.

The local cumulative budget ledger remains authoritative across runs. A run may
carry a compact snapshot retaining cumulative elapsed/credit limits/reserve and
an immutable link/hash to prior operations; stage deltas must be reconciled back
into that original ledger before another run. Never reset historical accounting
or treat task termination as proof of SQL/transaction termination.

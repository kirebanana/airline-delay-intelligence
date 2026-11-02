# Secret-free connectivity probe

This is not a data workload or an authenticated Snowflake test. It checks the
task role, selected S3 manifest bytes, denied Terraform-state HEAD, verified
Snowflake TLS and conditional encrypted report creation. ECR pull success is
verified separately from the actual ECS task. It retrieves no secret values.

Dependencies are exported from the project lock:

```sh
uv export --locked --extra cloud --no-dev --no-emit-project --no-header \
  --output-file containers/probe/requirements.txt
```

Build with an allowlisted temporary context containing only this Dockerfile,
requirements, `src/airline_warehouse/connectivity_probe.py` and
`tests/test_connectivity_probe.py`, preserving their relative paths. The supplied
Dockerfile-specific ignore file supports modern builders; do not rely on it with
the legacy builder or send the whole workspace as the context.

Offline qualification (no credentials or mounted files):

```sh
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 64 --memory 256m --cpus 0.25 \
  --entrypoint python airline-connectivity-probe:local \
  -m unittest discover -s tests -v
```

Live execution requires a separately reviewed image/deployment/run plan. Supply
only the five secret-free request fields documented in the module. The absolute
deadline is at most 120 seconds away and enforced by a Linux process timer;
the external supervisor must also stop tasks that never reach Python (e.g. pull
or startup failure). Results explicitly state `snowflake_authenticated: false`.
Neither TLS success nor state HEAD denial proves staged-result compatibility or
that every possible state access path is denied.

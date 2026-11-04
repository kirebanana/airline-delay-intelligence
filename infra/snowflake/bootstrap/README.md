# One-time user importer correction

**2026-11-04: authorized for real owner-run plan preparation only. No apply approval.**
This is not a permanent fork, a global provider replacement, or a reason to bypass
the exact three-import/zero-update saved-plan gate.

The official Snowflake provider 2.21.0 imports `mins_to_unlock` as null while its
schema defaults to the internal `-1` sentinel. Its custom diff still detects that
change even when Terraform ignores the timer; an apparent computed-output update
attempts `ALTER USER ... UNSET MINS_TO_UNLOCK`. Both original owner plans are unsafe.

`import-default.patch` initializes the provider's own default during import. It
does not issue DDL, change a Snowflake timer, or edit protected Terraform state.
There are no ignored user attributes in the resulting project configuration.

## Exact build provenance

- Source: `https://github.com/snowflakedb/terraform-provider-snowflake`.
- Tag `v2.21.0`, commit `ba89f50071b3b30bde94dbb83d8eef0b065fb9d5`.
- Compiler: official Go **1.26.10**, Linux amd64 archive SHA-256
  `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5`;
  checked against `https://go.dev/dl/?mode=json&include=all` before extraction.
- Binary SHA-256:
  `943cb3bb65cf8fb244a1e60437f9fa168f232f4bf61e91dc56082eaef1fe9943`.
- Build uses upstream `go.mod`/`go.sum`, readonly modules, the public Go checksum
  database, `CGO_ENABLED=0`, `GOTOOLCHAIN=local`, Linux amd64, and no private auth.

Reproduction, in a separate source checkout at the exact commit, with the verified
compiler available locally (tool download remains a separate authorization):

```bash
export GOTOOLCHAIN=local GOOS=linux GOARCH=amd64 GOAMD64=v1 CGO_ENABLED=0
export GOAUTH=off GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org
git apply /PATH/TO/import-default.patch
cp /PATH/TO/user_import_default_test.go pkg/resources/
go test -mod=readonly -p=2 ./pkg/resources -count=1
CGO_ENABLED=0 go build -mod=readonly -p=2 -trimpath -buildvcs=false \
  -ldflags='-X main.version=2.21.0-airline-importfix.1' \
  -o terraform-provider-snowflake_v2.21.0-airline-importfix.1 .
```

Do not use an unmatched rebuild. The bootstrap helper accepts only the reviewed
binary digest, copies it into an owner-only runtime directory outside Git, and
generates a **process-scoped** CLI configuration for that single directory. The
plan receipt binds that configuration, manifest, executable and source provenance
files in addition to the saved plan, HCL and unchanged official provider lock.

## Test evidence and return to the official provider

A regression test against the real importer failed before the patch for SERVICE,
PERSON and LEGACY_SERVICE, and passed after it. The provider's resource-unit suite
also passed. A local HTTP replay with dummy credentials and the three saved user
snapshots used the actual compiled plugin. Each user produced one import/no-op,
local import-only apply succeeded, and a subsequent normal plan using the untouched
official 2.21.0 binary exited zero/no-op. The test endpoint refused all mutation SQL;
the corrected runs attempted none. No real account was accessed for these tests.

Refresh-only replay displayed **No changes**, no resource drift/actions, and equal
serialized resource/output states (excluding snapshot serial/lineage), but Terraform
1.13.4 returned detailed exit code **2**. This caveat is recorded, not waived. Actual
post-adoption refresh verification remains required; do not claim exit-zero evidence.

After approval/apply of the eventual exact real plan, unset only the process-scoped
bootstrap configuration and return to the official provider. Keep the reviewed
bootstrap runtime protected as evidence; never replace the official installation,
edit the backend state to seed defaults, or publish binary plans/state/credentials.
See [owner procedure](../../../docs/snowflake-owner-adoption.md).

[Sanitized local-test evidence](../../../docs/evidence/snowflake-importer-bootstrap.json).

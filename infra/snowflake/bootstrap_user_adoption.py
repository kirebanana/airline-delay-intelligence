"""Pinned, one-time importer runtime; never install globally or authorize apply."""

import hashlib
import json
from pathlib import Path

BINARY_SHA256 = "943cb3bb65cf8fb244a1e60437f9fa168f232f4bf61e91dc56082eaef1fe9943"
UPSTREAM_COMMIT = "ba89f50071b3b30bde94dbb83d8eef0b065fb9d5"
BUILD_ROOT = Path("/tmp/opencode/airline-owner-provider-fix-20261104")
BINARY_NAME = "terraform-provider-snowflake_v2.21.0-airline-importfix.1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli_configuration(binary):
    return (
        "provider_installation {\n  dev_overrides {\n"
        '    "registry.terraform.io/snowflakedb/snowflake" = '
        + json.dumps(str(binary.parent))
        + "\n  }\n  direct {}\n}\n"
    )


def prepare_runtime(directory):
    """Copy only the approved binary into a protected, unambiguous runtime."""
    manifest = json.loads((BUILD_ROOT / "build-manifest.json").read_text())
    source = BUILD_ROOT / "bin" / BINARY_NAME
    if (
        manifest.get("upstream_commit") != UPSTREAM_COMMIT
        or manifest.get("binary_sha256") != BINARY_SHA256
        or sha(source) != BINARY_SHA256
    ):
        raise ValueError("One-time importer build differs from the reviewed local test artifact")
    directory.mkdir(mode=0o700, exist_ok=False)
    provider = directory / "provider"
    provider.mkdir(mode=0o700)
    binary = provider / BINARY_NAME
    with binary.open("xb") as stream:
        stream.write(source.read_bytes())
    binary.chmod(0o500)
    cli = directory / "bootstrap.tfrc"
    cli.write_text(cli_configuration(binary))
    cli.chmod(0o600)
    receipt = directory / "manifest.json"
    receipt.write_text(
        json.dumps(
            {
                "purpose": "one-time importer; explicit saved-plan approval still required",
                "upstream_commit": UPSTREAM_COMMIT,
                "binary": str(binary),
                "binary_sha256": BINARY_SHA256,
                "cli_config": str(cli),
                "cli_config_sha256": sha(cli),
                "return_to_official_provider_required": True,
            },
            indent=2,
        )
        + "\n"
    )
    receipt.chmod(0o600)
    return receipt


def runtime_files(receipt, cli_environment):
    """Bind the actual process override and executable, not just the provider lock."""
    receipt = receipt.resolve()
    data = json.loads(receipt.read_text())
    binary = Path(data["binary"]).resolve()
    cli = Path(data["cli_config"]).resolve()
    if (
        data.get("upstream_commit") != UPSTREAM_COMMIT
        or data.get("return_to_official_provider_required") is not True
        or data.get("binary_sha256") != BINARY_SHA256
        or sha(binary) != BINARY_SHA256
        or data.get("cli_config_sha256") != sha(cli)
        or cli.read_text() != cli_configuration(binary)
        or cli_environment is None
        or Path(cli_environment).resolve() != cli
        or binary.parent.parent != receipt.parent
        or cli.parent != receipt.parent
        or sorted(p.name for p in binary.parent.iterdir()) != [BINARY_NAME]
    ):
        raise ValueError("Bootstrap executable, CLI configuration or runtime binding changed")
    return [receipt, cli, binary]

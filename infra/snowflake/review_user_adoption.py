"""Review only: three exact user imports and no Snowflake remote changes."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from bootstrap_user_adoption import runtime_files

USERS = {
    "snowflake_service_user.builder": '"AIRLINE_DEV"',
    "snowflake_service_user.publisher": '"AIRLINE_PUBLISHER"',
    "snowflake_service_user.reader": '"AIRLINE_READER"',
}
STATIC = {
    'snowflake_account_role.service["AIRLINE_DEV_ROLE"]',
    'snowflake_account_role.service["AIRLINE_PUBLISHER_ROLE"]',
    'snowflake_account_role.service["AIRLINE_READER_ROLE"]',
    "snowflake_database.airline",
    "snowflake_file_format.bts",
    "snowflake_resource_monitor.budget",
    'snowflake_schema.builder["RAW"]',
    'snowflake_schema.builder["INGEST_TEST"]',
    "snowflake_schema.control",
    "snowflake_stage_external_s3.bts",
    "snowflake_storage_integration_aws.bts",
    "snowflake_warehouse.development",
}

REFRESH_METADATA = {
    "snowflake_resource_monitor.budget": {
        ("show_output", 0, "used_credits"),
        ("show_output", 0, "remaining_credits"),
    },
    "snowflake_warehouse.development": {
        ("show_output", 0, "resumed_on"),
        ("show_output", 0, "updated_on"),
    },
    "snowflake_stage_external_s3.bts": {("aws_access_point_arn",)},
}


def differences(before, after, path=()):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            yield from differences(before.get(key), after.get(key), (*path, key))
    elif isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for index, (old, new) in enumerate(zip(before, after, strict=True)):
            yield from differences(old, new, (*path, index))
    elif before != after:
        yield path, before, after


def review_refresh_metadata(drift):
    reviewed = []
    for resource in drift:
        address = resource.get("address")
        change = resource.get("change", {})
        if (
            address not in REFRESH_METADATA
            or resource.get("mode") != "managed"
            or resource.get("deposed")
            or resource.get("previous_address")
            or change.get("actions") != ["update"]
        ):
            raise ValueError("Unreviewed resource drift; stop adoption")
        paths = []
        for path, old, new in differences(change.get("before"), change.get("after")):
            if path not in REFRESH_METADATA[address]:
                raise ValueError(f"Unreviewed drift attribute on {address}")
            if path == ("aws_access_point_arn",) and (old is not None or new != ""):
                raise ValueError(
                    "Only observed null-to-empty access-point normalization is allowed"
                )
            paths.append(".".join(map(str, path)))
        if not paths:
            raise ValueError("Expected explicit refresh metadata differences")
        reviewed.append({"address": address, "attributes": paths})
    return reviewed


def inspect(plan, *, refresh=False):
    if plan.get("errored") or plan.get("complete") is False or plan.get("deferred_changes"):
        raise ValueError("Require a complete, successful, nondeferred plan")
    if any(c.get("status") != "pass" for c in plan.get("checks", [])):
        raise ValueError("All recorded plan checks must pass")
    if any(c.get("actions") != ["no-op"] for c in plan.get("output_changes", {}).values()):
        raise ValueError("Unexpected output changes")
    changes = plan.get("resource_changes", [])
    if len(changes) != 15 or {r.get("address") for r in changes} != STATIC | USERS.keys():
        raise ValueError(
            "Expected precisely twelve existing bindings and three exact user bindings"
        )
    imports = set()
    for resource in changes:
        change = resource["change"]
        if resource.get("deposed") or resource.get("previous_address"):
            raise ValueError("No deposed instances or address moves in this adoption")
        if resource.get("mode") != "managed" or change["actions"] != ["no-op"]:
            raise ValueError(
                f"Rejected remote action on {resource.get('address')}: {change['actions']}; "
                "no apply is authorized"
            )
        importing = change.get("importing")
        address = resource["address"]
        if importing:
            if refresh or address not in USERS or importing.get("id") != USERS[address]:
                raise ValueError("Unexpected import or identifier")
            imports.add(address)
        if address in USERS:
            after = change.get("after") or {}
            if after.get("name") != USERS[address].strip('"'):
                raise ValueError("Wrong existing user")
    if imports != (set() if refresh else set(USERS)):
        raise ValueError("Require exactly three imports, or zero after adoption")
    metadata = review_refresh_metadata(plan.get("resource_drift", []))
    return {
        "imports": len(imports),
        "remote_creates": 0,
        "remote_updates": 0,
        "remote_deletes": 0,
        "remote_replacements": 0,
        "managed_instances": 15,
        "refresh_only_review": refresh,
        "reviewed_refresh_metadata": metadata,
        "apply_authorized": False,
    }


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration_files(root):
    files = sorted(root.glob("*.tf"))
    if list(root.glob("*.tf.json")) or any(
        p.name == "override.tf" or p.name.endswith("_override.tf") for p in files
    ):
        raise ValueError("No JSON configuration or Terraform override files in this adoption")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--terraform", default="terraform")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--bootstrap-manifest", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sources = configuration_files(root)
    files = sources + [
        root / ".terraform.lock.hcl",
        Path(__file__).resolve(),
        root / "bootstrap_user_adoption.py",
    ]
    executable = shutil.which(args.terraform)
    if executable is None:
        raise ValueError("Terraform executable is unavailable")
    files.append(Path(executable).resolve())
    if args.bootstrap_manifest:
        files += runtime_files(args.bootstrap_manifest, os.environ.get("TF_CLI_CONFIG_FILE"))
        files += sorted(p for p in (root / "bootstrap").iterdir() if p.is_file())
    elif os.environ.get("TF_CLI_CONFIG_FILE"):
        raise ValueError("Unreviewed Terraform CLI configuration override")
    bindings = {str(p.resolve()): sha(p) for p in files + [args.plan.resolve()]}
    if args.verify:
        if json.loads(args.receipt.read_text())["file_sha256"] != bindings:
            raise ValueError("Saved plan, configuration, provider lock or reviewer changed")
        print("Exact reviewed binary and configuration hashes match; owner approval still required")
        return
    with zipfile.ZipFile(args.plan) as archive:
        archived = {
            n.removeprefix("tfconfig/m-/"): archive.read(n)
            for n in archive.namelist()
            if n.startswith("tfconfig/") and n != "tfconfig/modules.json"
        }
    expected = {p.name: p.read_bytes() for p in sources}
    if archived != expected:
        raise ValueError(
            "Saved Terraform configuration differs or contains an override/extra module"
        )
    raw = subprocess.check_output(
        [args.terraform, "show", "-json", str(args.plan.resolve())], cwd=root
    )
    if b"PRIVATE KEY-----" in raw:
        raise ValueError("Private authentication material must not appear in a saved plan")
    review = inspect(json.loads(raw), refresh=args.refresh)
    with args.receipt.open("x") as stream:
        stream.write(json.dumps({**review, "file_sha256": bindings}, indent=2) + "\n")
    args.receipt.chmod(0o600)
    print(
        json.dumps(
            {
                **review,
                "plan_sha256": sha(args.plan),
                "one_time_bootstrap": bool(args.bootstrap_manifest),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(f"PLAN REVIEW FAILED: {error}") from None

"""Owner-run plan only; never apply, grant privileges, or copy owner profiles."""

import argparse
import getpass
import json
import os
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

from bootstrap_user_adoption import prepare_runtime

from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection


def protected_key(path):
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Existing workload key permissions must be owner-only")
    return path.read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New protected evidence directory OUTSIDE either Git repo"
    )
    parser.add_argument("--owner-preflight-confirmed", action="store_true", required=True)
    parser.add_argument("--terraform", default="terraform")
    parser.add_argument("--verified-bootstrap", action="store_true")
    parser.add_argument("--prompt-owner-password", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    if not (root / ".terraform/terraform.tfstate").is_file():
        raise ValueError(
            "Use the already initialized protected backend; do not initialize a substitute"
        )
    if (
        any(k.startswith(("SNOWFLAKE_", "TF_CLI_ARGS")) for k in os.environ)
        or "TF_CLI_CONFIG_FILE" in os.environ
    ):
        raise ValueError(
            "Unset ambient Snowflake/CLI argument/configuration overrides before planning"
        )
    version = json.loads(subprocess.check_output([args.terraform, "version", "-json"], cwd=root))
    if version.get("terraform_version") != "1.13.4":
        raise ValueError("Use the verified Terraform 1.13.4 executable")
    output = args.output.expanduser().resolve()
    workspace = root.parents[2]
    if output == workspace or workspace in output.parents:
        raise ValueError("Keep owner plan/state evidence outside the Git workspace")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in ("TF_LOG", "TF_LOG_PATH", "TF_LOG_PROVIDER", "TF_LOG_CORE"):
        env.pop(key, None)
    runtime = None
    if args.verified_bootstrap:
        runtime = prepare_runtime(output / "runtime")
        env["TF_CLI_CONFIG_FILE"] = str(runtime.parent / "bootstrap.tfrc")
    if args.prompt_owner_password:
        if not sys.stdin.isatty():
            raise ValueError(
                "Enter the existing owner password only in an interactive local terminal"
            )
        password = getpass.getpass("Existing Snowflake owner password (hidden): ")
        if not password:
            raise ValueError("Owner password was empty; no plan attempted")
        env["TF_VAR_identity_owner_password"] = password
        env.pop("TF_VAR_identity_owner_passcode", None)
        del password
    # Existing workload auth stays scoped to its original providers. The separate
    # identity_owner profile is loaded by Terraform in the OWNER's terminal only.
    config = tomllib.loads((Path.home() / ".snowflake/config.toml").read_text())["connections"][
        "airline"
    ]
    env["TF_VAR_builder_private_key"] = protected_key(Path(config["private_key_file"]).expanduser())
    env["TF_VAR_publisher_private_key"] = protected_key(
        Path.home() / ".snowflake/airline-analytics/publisher.p8"
    )
    if "AIRLINE_KEY_PASSPHRASE" in env:
        env["TF_VAR_builder_key_passphrase"] = env["AIRLINE_KEY_PASSPHRASE"]
    public_keys = {}
    with connect_as("builder") as connection, DeadlineConnection(connection, 60).cursor() as cursor:
        cursor.execute("DESC INTEGRATION AIRLINE_BTS_S3")
        names = [item[0].lower() for item in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        env["TF_VAR_snowflake_external_id"] = next(
            row["property_value"] for row in rows if row["property"] == "STORAGE_AWS_EXTERNAL_ID"
        )
    for identity, name in (
        ("builder", "AIRLINE_DEV"),
        ("publisher", "AIRLINE_PUBLISHER"),
        ("reader", "AIRLINE_READER"),
    ):
        with (
            connect_as(identity) as connection,
            DeadlineConnection(connection, 60).cursor() as cursor,
        ):
            cursor.execute("DESC USER " + name)
            names = [item[0].lower() for item in cursor.description]
            properties = {
                row[names.index("property")]: row[names.index("value")] for row in cursor.fetchall()
            }
            if properties["TYPE"] != "SERVICE":
                raise ValueError("Existing user TYPE differs; do not repair it through adoption")
            public_keys[identity] = properties["RSA_PUBLIC_KEY"]
    env["TF_VAR_service_public_keys"] = json.dumps(public_keys)
    env.setdefault("AWS_PROFILE", "airline-old-dev")
    env["TF_INPUT"] = "0"
    # Do not inspect/copy the owner's profile or write credentials/tfvars to disk.
    backup = subprocess.check_output([args.terraform, "state", "pull"], cwd=root, env=env)
    if b"PRIVATE KEY-----" in backup:
        raise ValueError("Unexpected private key in state; stop")
    (output / "before.tfstate").write_bytes(backup)
    plan = output / "users.tfplan"
    subprocess.run(
        [
            args.terraform,
            "plan",
            "-input=false",
            "-no-color",
            "-parallelism=2",
            "-out=" + str(plan),
        ],
        cwd=root,
        env=env,
        check=True,
    )
    review_command = [
        sys.executable,
        str(root / "review_user_adoption.py"),
        str(plan),
        str(output / "review.json"),
        "--terraform",
        args.terraform,
    ]
    if runtime:
        review_command += ["--bootstrap-manifest", str(runtime)]
    reviewed = subprocess.run(
        review_command,
        cwd=root,
        env=env,
        check=False,
    )
    if reviewed.returncode:
        raise SystemExit(
            "Saved plan FAILED safety review. Nothing was applied; "
            "do not run the suggested apply command."
        )
    print(
        "STOP: no apply occurred. Have the exact plan hash reviewed and approved before applying."
    )


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(f"PLAN PREPARATION STOPPED: {error}") from None
    except subprocess.CalledProcessError:
        raise SystemExit("Terraform stopped with an error. Nothing was applied.") from None

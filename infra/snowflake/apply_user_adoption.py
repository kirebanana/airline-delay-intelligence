"""Apply only the owner-approved saved plan, then verify with the official provider."""

import base64
import getpass
import hashlib
import json
import os
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from plan_user_adoption import protected_key
from review_user_adoption import STATIC, USERS, differences, inspect, review_refresh_metadata
from verify_monitor import verify as verify_monitor

from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection

APPROVED_SHA = "684434be40060d3806a7494365438ed1a889b66ea488ac64f53f1b7bf1df4626"
DIRECTORY = "airline-user-adoption-bootstrap-20261104T135154Z"
TF = "/tmp/opencode/airline-tools/terraform"
ROOT = Path(__file__).resolve().parent
EPHEMERAL = {
    "builder_private_key",
    "publisher_private_key",
    "builder_key_passphrase",
    "identity_owner_password",
    "identity_owner_passcode",
}
PROPERTIES = (
    "NAME",
    "TYPE",
    "LOGIN_NAME",
    "DISPLAY_NAME",
    "DISABLED",
    "DEFAULT_WAREHOUSE",
    "DEFAULT_NAMESPACE",
    "DEFAULT_ROLE",
    "DEFAULT_SECONDARY_ROLES",
    "RSA_PUBLIC_KEY_FP",
    "RSA_PUBLIC_KEY_2_FP",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, default=str) + "\n")
    path.chmod(0o600)


def read_plan(path, env):
    raw = subprocess.check_output([TF, "show", "-json", str(path)], cwd=ROOT, env=env)
    if b"PRIVATE KEY-----" in raw:
        raise ValueError("Unexpected private authentication material in plan/state")
    return json.loads(raw)


def verify_approved(directory, env):
    plan = directory / "users.tfplan"
    if sha(plan) != APPROVED_SHA:
        raise ValueError("This is not the explicitly approved saved plan")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "review_user_adoption.py"),
            str(plan),
            str(directory / "review.json"),
            "--verify",
            "--terraform",
            TF,
            "--bootstrap-manifest",
            str(directory / "runtime/manifest.json"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Approved plan/configuration/runtime hash verification failed; no apply")
    parsed = read_plan(plan, env)
    inspect(parsed)
    return parsed


def refuse_repeat_apply(directory):
    if list(directory.glob("verification-*/apply-started.json")):
        raise ValueError("An apply was already attempted; review its evidence instead of rerunning")


def snapshot_identities():
    result = {}
    for identity, name in (
        ("builder", "AIRLINE_DEV"),
        ("publisher", "AIRLINE_PUBLISHER"),
        ("reader", "AIRLINE_READER"),
    ):
        with connect_as(identity) as connection, DeadlineConnection(connection, 60).cursor() as cur:
            cur.execute("DESC USER " + name)
            columns = [c[0].lower() for c in cur.description]
            properties = {
                r[columns.index("property")]: r[columns.index("value")] for r in cur.fetchall()
            }
            selected = {key: properties[key] for key in PROPERTIES}
            cur.execute("SHOW GRANTS TO USER " + name)
            columns = [c[0].lower() for c in cur.description]
            grants = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
            if any(row.get("grantee_name") != name or "role" not in row for row in grants):
                raise ValueError("Unexpected grant visibility/shape")
            grant_keys = (
                "role",
                "granted_to",
                "grantee_name",
                "granted_by",
                "granted_by_role_type",
            )
            grants = sorted(
                [{k: r[k] for k in grant_keys if k in r} for r in grants],
                key=lambda r: json.dumps(r, sort_keys=True),
            )
            cur.execute("SHOW PARAMETERS IN USER " + name)
            columns = [c[0].lower() for c in cur.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
            parameters = {r["key"]: {k: r[k] for k in ("value", "level")} for r in rows}
            result[identity] = {"properties": selected, "grants": grants, "parameters": parameters}
    return result


def nullish(value):
    return None if value is None or str(value).strip().lower() in ("", "null") else str(value)


def fingerprint(key):
    if not nullish(key):
        return None
    digest = hashlib.sha256(base64.b64decode(key, validate=True)).digest()
    return ("SHA256:" + base64.b64encode(digest).decode()).rstrip("=")


def match_live_users(plan, snapshot):
    for resource in plan["resource_changes"]:
        if resource["address"] not in USERS:
            continue
        identity = resource["address"].rsplit(".", 1)[1]
        properties = snapshot[identity]["properties"]
        after = resource["change"]["after"]
        if resource["change"]["before"] != after or properties["TYPE"] != "SERVICE":
            raise ValueError("Expected unchanged existing SERVICE user")
        for property_name, attribute in (
            ("NAME", "name"),
            ("LOGIN_NAME", "login_name"),
            ("DISPLAY_NAME", "display_name"),
            ("DISABLED", "disabled"),
            ("DEFAULT_WAREHOUSE", "default_warehouse"),
            ("DEFAULT_ROLE", "default_role"),
            ("DEFAULT_NAMESPACE", "default_namespace"),
        ):
            if nullish(properties[property_name]) != nullish(after.get(attribute)):
                raise ValueError(f"Live {identity} {property_name} changed since approval")
        if after.get("default_secondary_roles_option") != "ALL" or json.loads(
            properties["DEFAULT_SECONDARY_ROLES"]
        ) != ["ALL"]:
            raise ValueError("Existing secondary roles differ from the approved plan")
        for suffix in ("", "_2"):
            actual = nullish(properties["RSA_PUBLIC_KEY" + suffix + "_FP"])
            if (actual.rstrip("=") if actual else None) != fingerprint(
                after.get("rsa_public_key" + suffix)
            ):
                raise ValueError("Existing public-key fingerprint changed since approval")


def refresh_evidence(plan, path):
    """Inspect the real refresh-only JSON shape without weakening acceptance."""
    resources = (
        plan.get("prior_state", {}).get("values", {}).get("root_module", {}).get("resources", [])
    )
    module = plan.get("prior_state", {}).get("values", {}).get("root_module", {})
    inventory_matches = (
        {r.get("address") for r in resources} == STATIC | USERS.keys()
        and len(resources) == 15
        and all(r.get("mode") == "managed" for r in resources)
        and not module.get("child_modules")
    )
    with zipfile.ZipFile(path) as archive:
        states = [json.loads(archive.read(name)) for name in ("tfstate-prev", "tfstate")]
    for state in states:
        state.pop("serial", None)
        state.pop("lineage", None)
    return {
        "inventory_matches": inventory_matches,
        "no_resource_actions": not plan.get("resource_changes"),
        "no_observed_drift": not plan.get("resource_drift"),
        "no_output_changes": not plan.get("output_changes"),
        "serialized_states_equal_excluding_serial_lineage": states[0] == states[1],
        "plan_successful": not plan.get("errored") and plan.get("complete") is not False,
    }


def review_normal_after_import(plan):
    # Workload authentication legitimately advances this read-only observation.
    # Every planned resource action must still be no-op, with zero new imports.
    metadata = []
    for drift in plan.get("resource_drift", []):
        if drift.get("address") not in USERS:
            metadata.extend(review_refresh_metadata([drift]))
            continue
        change = drift.get("change", {})
        paths = [path for path, _, _ in differences(change.get("before"), change.get("after"))]
        if (
            drift.get("mode") != "managed"
            or drift.get("deposed")
            or drift.get("previous_address")
            or change.get("actions") != ["update"]
            or paths != [("show_output", 0, "last_success_login")]
        ):
            raise ValueError("Unreviewed post-import user drift; no further apply")
        metadata.append(
            {"address": drift["address"], "attributes": ["show_output.0.last_success_login"]}
        )
    checked = inspect({**plan, "resource_drift": []}, refresh=True)
    checked["reviewed_refresh_metadata"] = metadata
    return checked


def main():
    if not sys.stdin.isatty():
        raise ValueError("Run in the owner's local terminal; never provide passwords in chat")
    if (
        any(k.startswith(("SNOWFLAKE_", "TF_CLI_ARGS")) for k in os.environ)
        or "TF_CLI_CONFIG_FILE" in os.environ
    ):
        raise ValueError("Unset ambient Snowflake/Terraform override variables first")
    os.umask(0o077)
    directory = Path.home() / ".local/state" / DIRECTORY
    refuse_repeat_apply(directory)
    runtime = json.loads((directory / "runtime/manifest.json").read_text())
    env = os.environ.copy()
    for key in ("TF_LOG", "TF_LOG_PATH", "TF_LOG_CORE", "TF_LOG_PROVIDER"):
        env.pop(key, None)
    env["TF_CLI_CONFIG_FILE"] = runtime["cli_config"]
    env.setdefault("AWS_PROFILE", "airline-old-dev")
    env["TF_INPUT"] = "0"
    print("Checking the exact approved saved plan and runtime...", flush=True)
    plan = verify_approved(directory, env)
    print("Checking existing user defaults, keys, grants and parameters (read-only)...", flush=True)
    before = snapshot_identities()
    match_live_users(plan, before)
    with connect_as("publisher") as connection:
        monitor_before = verify_monitor(connection)
    output = directory / ("verification-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(mode=0o700, exist_ok=False)
    write_json(output / "identities-before.json", before)
    write_json(output / "monitor-before.json", monitor_before)
    for key, item in plan.get("variables", {}).items():
        value = item.get("value")
        if key in EPHEMERAL:
            if value is not None:
                raise ValueError("Unexpected saved ephemeral credential value")
            continue
        env["TF_VAR_" + key] = value if isinstance(value, str) else json.dumps(value)
    config = tomllib.loads((Path.home() / ".snowflake/config.toml").read_text())["connections"][
        "airline"
    ]
    env["TF_VAR_builder_private_key"] = protected_key(Path(config["private_key_file"]).expanduser())
    env["TF_VAR_publisher_private_key"] = protected_key(
        Path.home() / ".snowflake/airline-analytics/publisher.p8"
    )
    if "AIRLINE_KEY_PASSPHRASE" in env:
        env["TF_VAR_builder_key_passphrase"] = env["AIRLINE_KEY_PASSPHRASE"]
    password = getpass.getpass("Existing Snowflake owner password (hidden; local use only): ")
    if not password:
        raise ValueError("Password empty; no apply attempted")
    env["TF_VAR_identity_owner_password"] = password
    env.pop("TF_VAR_identity_owner_passcode", None)
    del password
    verify_approved(directory, env)
    write_json(output / "apply-started.json", {"approved_plan_sha256": APPROVED_SHA})
    applied = subprocess.run(
        [
            TF,
            "apply",
            "-input=false",
            "-no-color",
            "-lock-timeout=30s",
            "-parallelism=2",
            str(directory / "users.tfplan"),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        timeout=300,
    )
    write_json(
        output / "apply-result.json", {"exit_code": applied.returncode, "plan_sha256": APPROVED_SHA}
    )
    if applied.returncode:
        raise ValueError(
            "Apply did not complete successfully; do not retry or generate another apply"
        )
    # Explicit standard configuration excludes any global development override.
    # Existing official installation and checksum lock remain untouched.
    official = output / "official.tfrc"
    official.write_text("provider_installation {\n  direct {}\n}\n")
    official.chmod(0o600)
    env["TF_CLI_CONFIG_FILE"] = str(official)
    print(
        "Import completed. Returning to the official provider for read-only checks...", flush=True
    )
    results = {
        "apply_completed": True,
        "approved_plan_sha256": APPROVED_SHA,
        "bootstrap_override_removed": True,
        "evidence_directory": str(output),
        "apply_helper_sha256": sha(Path(__file__).resolve()),
    }
    for label, flags in (("normal", []), ("refresh", ["-refresh-only"])):
        saved = output / (label + ".tfplan")
        checked = subprocess.run(
            [
                TF,
                "plan",
                "-input=false",
                "-no-color",
                "-detailed-exitcode",
                "-parallelism=2",
                *flags,
                "-out=" + str(saved),
            ],
            cwd=ROOT,
            env=env,
            check=False,
            timeout=300,
        )
        results[label + "_exit_code"] = checked.returncode
        if checked.returncode not in (0, 2):
            write_json(output / "verification-incomplete.json", results)
            raise ValueError(
                "Import completed, but official-provider verification errored; no further apply"
            )
        parsed = read_plan(saved, env)
        if label == "normal":
            try:
                reviewed = review_normal_after_import(parsed)
                write_json(output / "normal-review.json", reviewed)
                results["normal_review_passed"] = True
                results["normal_review"] = {
                    key: reviewed[key]
                    for key in (
                        "imports",
                        "managed_instances",
                        "remote_creates",
                        "remote_updates",
                        "remote_deletes",
                        "remote_replacements",
                        "reviewed_refresh_metadata",
                    )
                }
            except ValueError as error:
                results["normal_review_passed"] = False
                results["normal_review_error"] = str(error)
        else:
            results["refresh_evidence"] = refresh_evidence(parsed, saved)
    after = snapshot_identities()
    write_json(output / "identities-after.json", after)
    results["identity_defaults_keys_grants_parameters_unchanged"] = before == after
    with connect_as("publisher") as connection:
        results["monitor"] = verify_monitor(connection)
    results["monitor_configuration_unchanged"] = results["monitor"] == monitor_before
    results["final_verification_passed"] = (
        results["normal_exit_code"] == 0
        and results["normal_review_passed"]
        and results["refresh_exit_code"] == 0
        and all(results["refresh_evidence"].values())
        and before == after
        and results["monitor_configuration_unchanged"]
    )
    write_json(output / "summary.json", results)
    print(json.dumps(results, indent=2))
    print("No verification plan was applied. Keep raw state/plans and credentials out of chat/Git.")
    if not results["final_verification_passed"]:
        raise SystemExit("IMPORT COMPLETED; final verification needs review. Do not rerun apply.")
    print("IMPORT AND OFFICIAL-PROVIDER VERIFICATION PASSED.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise SystemExit(
            f"STOPPED: {error}. Check the protected evidence; do not assume apply was undone."
        ) from None

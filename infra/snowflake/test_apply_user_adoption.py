"""Offline safety checks for the exact-plan owner apply launcher."""

import base64
import copy
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import apply_user_adoption as apply_module
from apply_user_adoption import (
    fingerprint,
    match_live_users,
    refresh_evidence,
    refuse_repeat_apply,
    review_normal_after_import,
    verify_approved,
)
from review_user_adoption import STATIC, USERS


class ApprovedApplyTests(unittest.TestCase):
    def test_wrong_plan_hash_cannot_reach_terraform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "users.tfplan").write_bytes(b"not-the-approved-plan")
            with patch("apply_user_adoption.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    verify_approved(root, {})
                run.assert_not_called()

    def test_changed_receipt_or_runtime_cannot_reach_plan_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("apply_user_adoption.sha") as sha,
                patch("apply_user_adoption.subprocess.run") as run,
                patch("apply_user_adoption.read_plan") as read,
            ):
                from apply_user_adoption import APPROVED_SHA

                sha.return_value = APPROVED_SHA
                run.return_value.returncode = 1
                with self.assertRaises(ValueError):
                    verify_approved(Path(directory), {})
                read.assert_not_called()
                command = run.call_args.args[0]
                self.assertIn("--verify", command)
                self.assertNotIn("apply", command)

    def test_previous_apply_attempt_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refuse_repeat_apply(root)
            previous = root / "verification-previous"
            previous.mkdir()
            (previous / "apply-started.json").write_text("{}")
            with self.assertRaises(ValueError):
                refuse_repeat_apply(root)

    def user_fixture(self):
        key = base64.b64encode(b"offline-public-key-fixture").decode()
        after = dict(
            name="AIRLINE_DEV",
            login_name="AIRLINE_DEV",
            display_name="AIRLINE_DEV",
            disabled="false",
            default_warehouse="AIRLINE_DEV_WH",
            default_role="AIRLINE_DEV_ROLE",
            default_namespace="",
            default_secondary_roles_option="ALL",
            rsa_public_key=key,
            rsa_public_key_2="",
            user_type="SERVICE",
        )
        properties = dict(
            NAME="AIRLINE_DEV",
            TYPE="SERVICE",
            LOGIN_NAME="AIRLINE_DEV",
            DISPLAY_NAME="AIRLINE_DEV",
            DISABLED="false",
            DEFAULT_WAREHOUSE="AIRLINE_DEV_WH",
            DEFAULT_ROLE="AIRLINE_DEV_ROLE",
            DEFAULT_NAMESPACE="null",
            DEFAULT_SECONDARY_ROLES='["ALL"]',
            RSA_PUBLIC_KEY_FP=fingerprint(key),
            RSA_PUBLIC_KEY_2_FP="null",
        )
        plan = {
            "resource_changes": [
                {
                    "address": "snowflake_service_user.builder",
                    "change": {"before": copy.deepcopy(after), "after": after},
                }
            ]
        }
        return plan, {"builder": {"properties": properties}}

    def test_matching_live_user_is_accepted(self):
        plan, snapshot = self.user_fixture()
        match_live_users(plan, snapshot)

    def test_changed_type_defaults_key_or_secondary_roles_stop_apply(self):
        for key, value in (
            ("TYPE", "PERSON"),
            ("DEFAULT_ROLE", "ACCOUNTADMIN"),
            ("RSA_PUBLIC_KEY_FP", "SHA256:changed"),
            ("DEFAULT_SECONDARY_ROLES", "[]"),
        ):
            plan, snapshot = self.user_fixture()
            snapshot["builder"]["properties"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                match_live_users(plan, snapshot)

    def test_malformed_public_key_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            fingerprint("not a base64 public key")

    def refresh_fixture(self, directory, *, changed=False):
        resources = [
            {"address": address, "mode": "managed"} for address in sorted(STATIC | USERS.keys())
        ]
        plan = {
            "complete": True,
            "errored": False,
            "prior_state": {"values": {"root_module": {"resources": resources}}},
        }
        before = {
            "serial": 0,
            "lineage": "",
            "resources": [{"attributes": {"name": "unchanged"}}],
            "outputs": {},
        }
        after = copy.deepcopy(before)
        after.update(serial=42, lineage="current-lineage")
        if changed:
            after["resources"][0]["attributes"]["name"] = "different"
        path = Path(directory) / "refresh.tfplan"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("tfstate-prev", json.dumps(before))
            archive.writestr("tfstate", json.dumps(after))
        return plan, path

    def test_actual_refresh_shape_is_read_without_normal_change_list(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path = self.refresh_fixture(directory)
            self.assertTrue(all(refresh_evidence(plan, path).values()))
            plan["resource_drift"] = [{"address": "unexpected"}]
            self.assertFalse(refresh_evidence(plan, path)["no_observed_drift"])
            plan["prior_state"]["values"]["root_module"]["resources"].pop()
            self.assertFalse(refresh_evidence(plan, path)["inventory_matches"])

    def test_real_serialized_attribute_difference_is_not_bookkeeping(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, path = self.refresh_fixture(directory, changed=True)
            self.assertFalse(
                refresh_evidence(plan, path)["serialized_states_equal_excluding_serial_lineage"]
            )

    def test_normal_review_allows_only_read_only_login_timestamp_drift(self):
        plan = {
            "resource_changes": [
                {
                    "address": address,
                    "mode": "managed",
                    "change": {
                        "actions": ["no-op"],
                        "after": {"name": USERS[address].strip('"')} if address in USERS else {},
                    },
                }
                for address in sorted(STATIC | USERS.keys())
            ],
            "resource_drift": [
                {
                    "address": "snowflake_service_user.builder",
                    "mode": "managed",
                    "change": {
                        "actions": ["update"],
                        "before": {"show_output": [{"last_success_login": "previous"}]},
                        "after": {"show_output": [{"last_success_login": "current"}]},
                    },
                }
            ],
        }
        self.assertEqual(review_normal_after_import(plan)["imports"], 0)
        changed = copy.deepcopy(plan)
        changed["resource_drift"][0]["change"]["after"]["default_role"] = "ACCOUNTADMIN"
        with self.assertRaises(ValueError):
            review_normal_after_import(changed)
        plan["resource_changes"][0]["change"]["actions"] = ["update"]
        with self.assertRaises(ValueError):
            review_normal_after_import(plan)


class ApplyWorkflowTests(unittest.TestCase):
    def run_workflow(self, home, refresh_exit):
        directory = home / ".local/state" / apply_module.DIRECTORY
        (directory / "runtime").mkdir(parents=True)
        cli = directory / "runtime/bootstrap.tfrc"
        (directory / "runtime/manifest.json").write_text(json.dumps({"cli_config": str(cli)}))
        (home / ".snowflake").mkdir()
        (home / ".snowflake/config.toml").write_text(
            '[connections.airline]\nprivate_key_file = "dummy.p8"\n'
        )
        normal = {
            "resource_changes": [
                {
                    "address": address,
                    "mode": "managed",
                    "change": {
                        "actions": ["no-op"],
                        "after": {"name": USERS[address].strip('"')} if address in USERS else {},
                    },
                }
                for address in sorted(STATIC | USERS.keys())
            ]
        }
        calls = []

        def run(command, **kwargs):
            calls.append((list(command), dict(kwargs["env"])))
            code = refresh_exit if "-refresh-only" in command else 0
            return type("Result", (), {"returncode": code})()

        stream = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"HOME": str(home)}, clear=True))
            stack.enter_context(patch("sys.stdin.isatty", return_value=True))
            stack.enter_context(
                patch.object(apply_module, "verify_approved", return_value={"variables": {}})
            )
            stack.enter_context(
                patch.object(apply_module, "snapshot_identities", return_value={"offline": "same"})
            )
            stack.enter_context(patch.object(apply_module, "match_live_users"))
            stack.enter_context(
                patch.object(apply_module, "protected_key", return_value="NOT_A_REAL_KEY")
            )
            stack.enter_context(
                patch.object(apply_module.getpass, "getpass", return_value="NOT_A_REAL_PASSWORD")
            )
            stack.enter_context(patch.object(apply_module.subprocess, "run", side_effect=run))
            stack.enter_context(patch.object(apply_module, "read_plan", side_effect=[normal, {}]))
            stack.enter_context(
                patch.object(apply_module, "refresh_evidence", return_value={"all_checks": True})
            )
            stack.enter_context(patch.object(apply_module, "connect_as"))
            stack.enter_context(
                patch.object(apply_module, "verify_monitor", return_value={"level": "ACCOUNT"})
            )
            stack.enter_context(redirect_stdout(stream))
            if refresh_exit:
                with self.assertRaisesRegex(SystemExit, "IMPORT COMPLETED"):
                    apply_module.main()
            else:
                apply_module.main()
        summary_path = next(directory.glob("verification-*/summary.json"))
        self.assertNotIn("NOT_A_REAL_PASSWORD", stream.getvalue())
        self.assertNotIn("NOT_A_REAL_PASSWORD", summary_path.read_text())
        return calls, json.loads(summary_path.read_text()), cli, directory

    def test_single_exact_apply_then_official_plans_no_other_applies(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, summary, bootstrap_cli, evidence = self.run_workflow(Path(directory), 0)
            self.assertEqual(len(calls), 3)
            self.assertEqual([c[0][1] for c in calls], ["apply", "plan", "plan"])
            self.assertEqual(calls[0][0][-1], str(evidence / "users.tfplan"))
            self.assertEqual(calls[0][1]["TF_CLI_CONFIG_FILE"], str(bootstrap_cli))
            self.assertNotEqual(calls[1][1]["TF_CLI_CONFIG_FILE"], str(bootstrap_cli))
            self.assertNotIn("dev_overrides", Path(calls[1][1]["TF_CLI_CONFIG_FILE"]).read_text())
            self.assertTrue(summary["final_verification_passed"])
            with self.assertRaises(ValueError):
                refuse_repeat_apply(evidence)

    def test_refresh_exit_two_remains_pending_not_silently_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, summary, _, _ = self.run_workflow(Path(directory), 2)
            self.assertEqual(sum("apply" in command for command, _ in calls), 1)
            self.assertTrue(summary["apply_completed"])
            self.assertEqual(summary["refresh_exit_code"], 2)
            self.assertFalse(summary["final_verification_passed"])


if __name__ == "__main__":
    unittest.main()

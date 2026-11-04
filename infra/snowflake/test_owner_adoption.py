"""Offline tests; run explicitly from the static infrastructure directory."""

import copy
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import bootstrap_user_adoption as bootstrap
from review_user_adoption import STATIC, USERS, configuration_files, inspect
from verify_monitor import verify


class AdoptionReviewTests(unittest.TestCase):
    def plan(self):
        resources = [
            {"address": a, "mode": "managed", "change": {"actions": ["no-op"]}}
            for a in sorted(STATIC)
        ]
        resources += [
            {
                "address": a,
                "mode": "managed",
                "change": {
                    "actions": ["no-op"],
                    "importing": {"id": name},
                    "after": {"name": name.strip('"')},
                },
            }
            for a, name in USERS.items()
        ]
        return {"resource_changes": resources}

    def test_exact_three_imports(self):
        self.assertEqual(inspect(self.plan())["imports"], 3)

    def test_any_remote_change_is_refused(self):
        for actions in (["create"], ["update"], ["delete"], ["delete", "create"]):
            plan = self.plan()
            plan["resource_changes"][0]["change"]["actions"] = actions
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                inspect(plan)

    def test_missing_wrong_extra_or_drift_refused(self):
        base = self.plan()
        candidates = []
        plan = copy.deepcopy(base)
        plan["resource_changes"].pop()
        candidates.append(plan)
        plan = copy.deepcopy(base)
        plan["resource_changes"][-1]["change"]["importing"]["id"] = '"SOMEONE_ELSE"'
        candidates.append(plan)
        plan = copy.deepcopy(base)
        plan["resource_drift"] = [{"address": "unexpected"}]
        candidates.append(plan)
        for plan in candidates:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                inspect(plan)

    def test_clean_post_import_refresh(self):
        plan = self.plan()
        for item in plan["resource_changes"]:
            item["change"].pop("importing", None)
        self.assertEqual(inspect(plan, refresh=True)["imports"], 0)
        with self.assertRaises(ValueError):
            inspect(plan)

    def test_reviewed_refresh_metadata_is_not_a_remote_update(self):
        plan = self.plan()
        plan["resource_drift"] = [
            {
                "address": "snowflake_resource_monitor.budget",
                "mode": "managed",
                "change": {
                    "actions": ["update"],
                    "before": {"show_output": [{"used_credits": 4.57, "remaining_credits": 5.43}]},
                    "after": {"show_output": [{"used_credits": 6.20, "remaining_credits": 3.80}]},
                },
            },
            {
                "address": "snowflake_stage_external_s3.bts",
                "mode": "managed",
                "change": {
                    "actions": ["update"],
                    "before": {"aws_access_point_arn": None},
                    "after": {"aws_access_point_arn": ""},
                },
            },
            {
                "address": "snowflake_warehouse.development",
                "mode": "managed",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "show_output": [{"resumed_on": "previous", "updated_on": "previous"}]
                    },
                    "after": {"show_output": [{"resumed_on": "current", "updated_on": "current"}]},
                },
            },
        ]
        self.assertEqual(inspect(plan)["imports"], 3)
        for drift in plan["resource_drift"]:
            bad = copy.deepcopy(plan)
            item = next(x for x in bad["resource_drift"] if x["address"] == drift["address"])
            item["change"]["after"]["unexpected_security_setting"] = "changed"
            with self.subTest(address=drift["address"]), self.assertRaises(ValueError):
                inspect(bad)
        plan["resource_changes"][-1]["change"]["actions"] = ["update"]
        with self.assertRaises(ValueError):
            inspect(plan)

    def test_nonempty_access_point_is_not_normalization(self):
        plan = self.plan()
        plan["resource_drift"] = [
            {
                "address": "snowflake_stage_external_s3.bts",
                "mode": "managed",
                "change": {
                    "actions": ["update"],
                    "before": {"aws_access_point_arn": None},
                    "after": {"aws_access_point_arn": "arn:changed"},
                },
            }
        ]
        with self.assertRaises(ValueError):
            inspect(plan)

    def test_incomplete_failed_checks_outputs_and_deposed_refused(self):
        for update in (
            {"complete": False},
            {"errored": True},
            {"deferred_changes": [{"reason": "unknown"}]},
            {"checks": [{"status": "unknown"}]},
            {"output_changes": {"unexpected": {"actions": ["update"]}}},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                inspect({**self.plan(), **update})
        for field in ("deposed", "previous_address"):
            plan = self.plan()
            plan["resource_changes"][0][field] = "unexpected"
            with self.subTest(field=field), self.assertRaises(ValueError):
                inspect(plan)

    def test_override_files_refused_at_review_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tf").write_text("# source\n")
            self.assertEqual(len(configuration_files(root)), 1)
            for name in ("override.tf", "owner_override.tf", "extra.tf.json"):
                path = root / name
                path.write_text("{}")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    configuration_files(root)
                path.unlink()


class MonitorVerificationTests(unittest.TestCase):
    def check(self, **updates):
        row = dict(
            name="AIRLINE_BUDGET",
            level="ACCOUNT",
            credit_quota="10.00",
            frequency="MONTHLY",
            used_credits="6.19",
            suspend_at=None,
            suspend_immediately_at="100%",
        )
        row.update(updates)
        cursor = MagicMock()
        cursor.description = [(key,) for key in row]
        cursor.fetchall.return_value = [tuple(row.values())]
        wrapper = MagicMock()
        wrapper.cursor.return_value.__enter__.return_value = cursor
        with patch("verify_monitor.DeadlineConnection", return_value=wrapper):
            result = verify(object())
        cursor.execute.assert_called_once_with("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
        return result

    def test_exact_monitor_read_only(self):
        self.assertEqual(self.check()["credit_quota"], "10.00")

    def test_wrong_attachment_or_changed_budget_refused(self):
        for update in (
            {"level": "WAREHOUSE"},
            {"credit_quota": "20"},
            {"frequency": "DAILY"},
            {"suspend_immediately_at": "90%"},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.check(**update)


class BootstrapRuntimeTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "build"
            (build / "bin").mkdir(parents=True)
            binary = build / "bin" / bootstrap.BINARY_NAME
            binary.write_bytes(b"offline-unit-test-binary-not-executed")
            digest = bootstrap.sha(binary)
            (build / "build-manifest.json").write_text(
                json.dumps(
                    {
                        "upstream_commit": bootstrap.UPSTREAM_COMMIT,
                        "binary_sha256": digest,
                    }
                )
            )
            with (
                patch.object(bootstrap, "BUILD_ROOT", build),
                patch.object(bootstrap, "BINARY_SHA256", digest),
            ):
                receipt = bootstrap.prepare_runtime(root / "runtime")
                yield receipt, json.loads(receipt.read_text())

    def test_pinned_runtime_is_bound_to_exact_process_configuration(self):
        with self.fixture() as (receipt, data):
            files = bootstrap.runtime_files(receipt, data["cli_config"])
            self.assertEqual(len(files), 3)
            self.assertEqual(Path(data["binary"]).stat().st_mode & 0o777, 0o500)
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            for value in (None, str(receipt.parent / "unreviewed.tfrc")):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    bootstrap.runtime_files(receipt, value)

    def test_binary_config_and_extra_executable_tampering_refused(self):
        for change in ("binary", "cli", "extra", "manifest"):
            with self.subTest(change=change), self.fixture() as (receipt, data):
                if change == "binary":
                    binary = Path(data["binary"])
                    binary.chmod(0o700)
                    binary.write_bytes(b"different-runtime")
                elif change == "cli":
                    cli = Path(data["cli_config"])
                    cli.write_text(cli.read_text() + "# changed configuration\n")
                    data["cli_config_sha256"] = bootstrap.sha(cli)
                    receipt.write_text(json.dumps(data))
                elif change == "extra":
                    (Path(data["binary"]).parent / "terraform-provider-snowflake_other").write_text(
                        "unexpected"
                    )
                else:
                    data["return_to_official_provider_required"] = False
                    receipt.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    bootstrap.runtime_files(receipt, data["cli_config"])

    def test_unreviewed_build_refused_before_runtime_creation(self):
        with self.fixture() as (receipt, _):
            source = bootstrap.BUILD_ROOT / "bin" / bootstrap.BINARY_NAME
            source.write_bytes(b"unexpected-source-binary")
            target = receipt.parent.parent / "other-runtime"
            with self.assertRaises(ValueError):
                bootstrap.prepare_runtime(target)
            self.assertFalse(target.exists())

    def test_no_ignored_user_attributes(self):
        users = Path(__file__).with_name("users.tf").read_text()
        self.assertNotIn("ignore_changes", users)
        self.assertEqual(users.count("prevent_destroy = true"), 3)


if __name__ == "__main__":
    unittest.main()

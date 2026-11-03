"""Credential-free delivery boundary tests; live signed-token checks run separately."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deliver", ROOT / "infra/jobs/deliver.py")
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def test_provider_refresh_has_required_read_permissions(self):
        policy = (ROOT / "infra/ingestion/delivery.tf").read_text()
        self.assertIn('Action = "ecs:DescribeTaskDefinition", Resource = "*"', policy)
        self.assertIn('"states:ListStateMachineVersions"', policy)
        self.assertIn('Action = "states:ValidateStateMachineDefinition", Resource = "*"', policy)

    def test_trust_uses_immutable_repository_subject(self):
        policy = (ROOT / "infra/ingestion/delivery.tf").read_text()
        self.assertIn(
            "repo:kirebanana@173084883/airline-delay-intelligence@1433493412:environment:release",
            policy,
        )
        self.assertNotIn('"repo:kirebanana/airline-delay-intelligence:environment:release"', policy)

    def test_only_authorization_errors_prove_denial(self):
        for code in ["AccessDenied", "AccessDeniedException", "InvalidIdentityToken"]:
            denied = Mock(side_effect=ClientError({"Error": {"Code": code}}, "Probe"))
            self.assertEqual(delivery.expect_denied(denied), code)
        unavailable = Mock(side_effect=ClientError({"Error": {"Code": "Throttling"}}, "Probe"))
        with self.assertRaises(ClientError):
            delivery.expect_denied(unavailable)

    def test_unexpected_success_fails_closed(self):
        with self.assertRaises(RuntimeError):
            delivery.expect_denied(lambda: {})

    def test_untrusted_login_never_requests_token(self):
        for change in [
            {"GITHUB_REF": "refs/heads/untrusted"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_REPOSITORY": "someone/fork"},
        ]:
            env = {
                "GITHUB_REPOSITORY": "kirebanana/airline-delay-intelligence",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                **change,
            }
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(delivery, "assume") as assume,
            ):
                with self.assertRaises(ValueError):
                    delivery.login()
                assume.assert_not_called()

    def test_container_has_no_network_or_privilege(self):
        with patch.object(delivery, "run") as run:
            delivery.container("digest", "-m", "unittest")
        args = run.call_args.args
        self.assertIn("--read-only", args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertEqual(args[args.index("--cap-drop") + 1], "ALL")

    def test_credentials_never_exist_in_validation_workflow(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        for forbidden in [
            "id-token:",
            "secrets.",
            "deliver.py",
            "terraform apply",
            "workflow_run:",
        ]:
            self.assertNotIn(forbidden, workflow)

    def test_promotion_only_accepts_protected_main_code_or_manual_dispatch(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        for forbidden in ["  pull_request:", "  schedule:", "workflow_run:"]:
            self.assertNotIn(forbidden, workflow)
        self.assertIn("  push:", workflow)
        self.assertIn("    branches: [main]", workflow)
        self.assertIn("    paths:", workflow)
        self.assertIn("environment: release", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_active_refresh_refuses_promotion_before_mutations(self):
        sfn = Mock()
        sfn.list_executions.return_value = {"executions": [{"status": "RUNNING"}]}
        with patch.object(delivery.boto3, "client", return_value=sfn):
            with self.assertRaisesRegex(ValueError, "active"):
                delivery.require_idle()

    def test_idle_requires_no_running_workflow_or_task(self):
        sfn, ecs = Mock(), Mock()
        sfn.list_executions.return_value = {"executions": []}
        ecs.list_tasks.return_value = {"taskArns": []}
        with patch.object(delivery.boto3, "client", side_effect=[sfn, ecs]):
            delivery.require_idle()
        ecs.list_tasks.return_value = {"taskArns": ["task"]}
        with patch.object(delivery.boto3, "client", side_effect=[sfn, ecs]):
            with self.assertRaisesRegex(ValueError, "active"):
                delivery.require_idle()


if __name__ == "__main__":
    unittest.main()

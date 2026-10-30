"""Real process/server uncertainty under explicit funding, isolated targets only."""

import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from airline_warehouse.budget import live_budget
from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.publication import Busy, claim, initialize, retire
from airline_warehouse.recovery import recover_local


@unittest.skipUnless(
    os.environ.get("AIRLINE_RECOVERY_LIVE") == "funded-13",
    "Requires funded own-session/process-death qualification",
)
class LocalRecoveryTests(unittest.TestCase):
    def test_server_statement_limit_is_carried_with_the_query(self):
        from snowflake.connector.errors import ProgrammingError

        budget = Path(os.environ["AIRLINE_BATCH_STATE"])
        with connect_as("builder") as conn, live_budget(conn, budget):
            with conn.cursor() as cur:
                # Keep the client allowance long enough to observe the SERVER's
                # own two-second limit, not client-side cancellation evidence.
                try:
                    cur.execute(
                        "SELECT SYSTEM$WAIT(10)",
                        timeout=15,
                        _statement_params={"STATEMENT_TIMEOUT_IN_SECONDS": 2},
                    )
                except ProgrammingError as error:
                    message = str(error)
                else:
                    message = "server limit did not terminate the query"
                status = conn.get_query_status(cur.sfqid).name
        self.assertEqual(status, "FAILED_WITH_ERROR")
        self.assertIn("timeout", message.lower())
        self.assertIn("2 second", message.lower())

    def test_lost_commit_and_post_commit_bookkeeping_failure_reconcile_without_rollback(self):
        from unittest.mock import patch

        from airline_warehouse.refresh import refresh
        from airline_warehouse.warehouse import processing_contract

        candidate_path = Path(os.environ["AIRLINE_TEST_CANDIDATE"])
        candidate = json.loads(candidate_path.read_text())
        self.assertEqual(candidate["processing_contract"], processing_contract())
        root = Path(os.environ["AIRLINE_RECOVERY_EVIDENCE"])
        budget = Path(os.environ["AIRLINE_BATCH_STATE"])
        for fault in ("commit_response", "status_write"):
            output = root / (fault + "-" + uuid.uuid4().hex[:16])
            target = "test_" + uuid.uuid4().hex[:16]
            with connect_as("publisher") as conn, live_budget(conn, budget) as remaining:
                initialize(DeadlineConnection(conn, remaining), target)
            state = {"selection": False, "fired": False}

            class FaultConnection:
                def __init__(self, conn, context, fault_kind, attempt_output):
                    self.conn = conn
                    self.context, self.fault_kind, self.attempt_output = (
                        context,
                        fault_kind,
                        attempt_output,
                    )

                def __getattr__(self, name):
                    return getattr(self.conn, name)

                def __enter__(self):
                    self.conn.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.conn.__exit__(*args)

                def cursor(self):
                    from test_live_publication import SQLFaultCursor

                    def hook(sql):
                        if "previous=active,active=" in sql:
                            self.context["selection"] = True
                        if (
                            sql == "COMMIT"
                            and self.context["selection"]
                            and not self.context["fired"]
                        ):
                            self.context["fired"] = True
                            if self.fault_kind == "commit_response":
                                raise OSError("Injected lost acknowledgment after real COMMIT")
                            (self.attempt_output / "result.json").mkdir()

                    return SQLFaultCursor(self.conn.cursor(), hook)

            def factory(
                kind,
                state=state,
                fault=fault,
                output=output,
                connection_class=FaultConnection,
                **kwargs,
            ):
                conn = connect_as(kind, **kwargs)
                return connection_class(conn, state, fault, output) if kind == "publisher" else conn

            with patch("airline_warehouse.refresh.connect_as", factory):
                if fault == "commit_response":
                    result = refresh(
                        [Path(os.environ["AIRLINE_TEST_ARTIFACT"])],
                        output,
                        budget,
                        target,
                        uuid.uuid4().hex,
                        stage="publish",
                        candidate_path=candidate_path,
                    )
                    self.assertEqual(result["status"], "PUBLISHED")
                else:
                    with self.assertRaises(OSError):
                        refresh(
                            [Path(os.environ["AIRLINE_TEST_ARTIFACT"])],
                            output,
                            budget,
                            target,
                            uuid.uuid4().hex,
                            stage="publish",
                            candidate_path=candidate_path,
                        )
                    self.assertTrue(json.loads(budget.read_text())["recovery_required"])
                    result = recover_local(output, budget)
                    self.assertEqual(result["publication"], "PUBLISHED")
                    self.assertFalse(json.loads(budget.read_text()).get("recovery_required"))
            self.assertTrue(state["fired"])

    def test_client_death_unknown_transaction_lost_query_id_and_safe_next_admission(self):
        root = Path(os.environ["AIRLINE_RECOVERY_EVIDENCE"])
        budget = Path(os.environ["AIRLINE_BATCH_STATE"])
        for lose_id in (False, True):
            with self.subTest(lost_query_id=lose_id):
                output = root / ("process-death-" + uuid.uuid4().hex[:16])
                output.mkdir(parents=True)
                intent = dict(
                    target="test_" + uuid.uuid4().hex[:16],
                    request_id=uuid.uuid4().hex,
                    attempt=uuid.uuid4().hex,
                    release_id=uuid.uuid4().hex,
                    inputs={},
                    processing_contract="recovery-fixture",
                    weather=None,
                )
                (output / "intent.json").write_text(json.dumps(intent))
                with connect_as("publisher") as conn, live_budget(conn, budget) as remaining:
                    initialize(DeadlineConnection(conn, remaining), intent["target"])
                env = os.environ.copy()
                if lose_id:
                    env["AIRLINE_TEST_LOST_QUERY_ID"] = "1"
                child = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).with_name("recovery_child.py")),
                        str(output),
                        str(budget),
                    ],
                    env=env,
                    capture_output=True,
                    timeout=90,
                )
                self.assertEqual(child.returncode, 79, child.stderr.decode())
                submitted = json.loads((output / "submitted.json").read_text())
                with connect_as("publisher") as conn:
                    with self.assertRaises(Busy):
                        claim(DeadlineConnection(conn, 30), intent["target"], uuid.uuid4().hex)
                result = recover_local(output, budget)
                self.assertEqual(result["publication"], "NOT_PUBLISHED")
                with connect_as("builder") as conn, live_budget(conn, budget) as remaining:
                    self.assertIn(
                        conn.get_query_status(submitted["query_id"]).name,
                        {"SUCCESS", "ABORTED", "FAILED_WITH_ERROR"},
                    )
                    with DeadlineConnection(conn, remaining).cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {submitted['table']}")
                        count = cur.fetchone()[0]
                self.assertEqual(
                    count, 0
                )  # session termination actually rolled back the transaction
                with connect_as("publisher") as conn, live_budget(conn, budget) as remaining:
                    newer = claim(
                        DeadlineConnection(conn, remaining), intent["target"], uuid.uuid4().hex
                    )
                # Stale recovery is idempotent and cannot retire a newer generation.
                recover_local(output, budget)
                with connect_as("publisher") as conn, live_budget(conn, budget) as remaining:
                    with self.assertRaises(Busy):
                        claim(
                            DeadlineConnection(conn, remaining), intent["target"], uuid.uuid4().hex
                        )
                    retire(DeadlineConnection(conn, remaining), newer, "FAILED")

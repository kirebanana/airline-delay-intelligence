import time
import unittest
from contextlib import contextmanager

from airline_warehouse.recovery import terminate_own_session


class TransactionRecoveryTests(unittest.TestCase):
    class Driver:
        def __init__(self, user="AIRLINE_PUBLISHER"):
            self.user = user
            self.aborted = False
            self.commands = []
            self.description = [(x,) for x in ("id", "user", "session", "state")]

        @contextmanager
        def cursor(self):
            yield self

        def execute(self, sql, params=None, **kwargs):
            self.commands.append((sql, params))
            if "SYSTEM$ABORT_TRANSACTION" in sql:
                self.aborted = True
            self.sql = sql

        def fetchone(self):
            return (
                "Aborted transaction id: 99"
                if "ABORT_TRANSACTION" in self.sql
                else "session [42] terminated.",
            )

        def fetchall(self):
            other = (100, "AIRLINE_PUBLISHER", 43, "running")
            return [other] if self.aborted else [(99, self.user, 42, "running"), other]

    def test_session_ack_is_not_transaction_proof_and_only_matching_own_transaction_is_aborted(
        self,
    ):
        conn = self.Driver()
        proof = terminate_own_session(conn, 42, "publisher", time.monotonic() + 30)
        aborts = [params for sql, params in conn.commands if "SYSTEM$ABORT_TRANSACTION" in sql]
        self.assertEqual(aborts, [(99,)])
        self.assertEqual(proof["aborted_transactions"], [99])
        self.assertTrue(proof["transactions_terminal"])

    def test_conflicting_originating_user_refuses_transaction_abort(self):
        conn = self.Driver("OTHER_USER")
        with self.assertRaises(ValueError):
            terminate_own_session(conn, 42, "publisher", time.monotonic() + 30)
        self.assertFalse(conn.aborted)

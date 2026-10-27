import copy
import hashlib
import unittest
from unittest.mock import MagicMock

from airline_warehouse.load import build_load_plan, check_validation, execute_load
from airline_warehouse.prepare import BTS_COLUMNS, LINEAGE


def manifest():
    result = {
        "manifest_version": 1,
        "preparation_contract": "bts-marketing-csv-v1",
        "source_kind": "official-local-import",
        "month": "2025-01",
        "rows": 599013,
        "source_sha256": "a" * 64,
        "prepared_sha256": "b" * 64,
        "loaded_artifact_id": "c" * 64,
        "prepared_columns": LINEAGE + BTS_COLUMNS,
        "source_columns": BTS_COLUMNS,
        "profile": {"den_rows": 24732, "den_cancelled": 313, "den_diverted": 69},
    }
    result["loaded_artifact_id"] = hashlib.sha256(
        f"{'a' * 64}:bts-marketing-csv-v1:{'b' * 64}".encode()
    ).hexdigest()
    return result


class LoadPlanTests(unittest.TestCase):
    def loader_connection(
        self,
        *,
        reuse=False,
        corrupt=False,
        commit_error=False,
        suspend=60,
        monitor_overrides=None,
        monitor_visible=True,
    ):
        """Connector boundary double; does not establish Snowflake SQL semantics."""
        good = {
            "ROWS": 599013,
            "DISTINCT_ORDINALS": 599013,
            "FIRST_ORDINAL": 1,
            "LAST_ORDINAL": 599013,
            "WRONG_SOURCE": 0,
            "WRONG_MONTH": 0,
            "MISMATCHED_FINGERPRINTS": 0,
            "DEN_ROWS": 24732,
            "DEN_CANCELLED": 313,
            "DEN_DIVERTED": 69,
        }
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        validations = 0

        def execute(sql):
            nonlocal validations
            if sql.startswith("SHOW WAREHOUSES"):
                data = {
                    "size": "X-Small",
                    "auto_suspend": suspend,
                    "enable_query_acceleration": False,
                    "resource_monitor": "null",  # account-level protection is sufficient
                }
            elif sql.startswith("SHOW RESOURCE MONITORS"):
                data = {
                    "name": "AIRLINE_BUDGET",
                    "level": "ACCOUNT",
                    "credit_quota": "5.0",
                    "used_credits": "0.0",
                    "suspend_at": "75%",
                    "suspend_immediately_at": "90%",
                    "notify_at": "50%",
                }
                data.update(monitor_overrides or {})
            elif sql.startswith("SHOW TABLES"):
                data = {
                    "comment": build_load_plan(manifest(), "airline-bts-336805808138-us-east-2")[
                        "table_comment"
                    ]
                }
            elif sql.startswith("SELECT"):
                validations += 1
                data = dict(good) if reuse or validations > 1 else dict.fromkeys(good, 0)
                if corrupt and validations > 1:
                    data["MISMATCHED_FINGERPRINTS"] = 1
            else:
                data = {}
            cur.description = [(k,) for k in data]
            cur.fetchone.return_value = tuple(data.values())
            cur.fetchall.return_value = (
                []
                if sql.startswith("SHOW RESOURCE MONITORS") and not monitor_visible
                else [tuple(data.values())]
            )
            cur.sfqid = "synthetic-query-id"
            if sql == "COMMIT" and commit_error:
                raise ConnectionError("Lost acknowledgment")
            return cur

        cur.execute.side_effect = execute
        return conn, cur

    def test_loader_commits_only_after_acceptance_and_reuses_complete_artifacts(self):
        for reuse in (False, True):
            conn, cur = self.loader_connection(reuse=reuse)
            result = execute_load(
                conn, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=True
            )
            statements = [c.args[0] for c in cur.execute.call_args_list]
            self.assertEqual(result["status"], "reused" if reuse else "accepted")
            self.assertEqual("COMMIT" in statements, not reuse)
            self.assertEqual(any(s.startswith("COPY INTO") for s in statements), not reuse)

    def test_loader_rolls_back_failed_acceptance_and_never_retries_unknown_commit(self):
        for corrupt, commit_error in ((True, False), (False, True)):
            conn, cur = self.loader_connection(corrupt=corrupt, commit_error=commit_error)
            with self.assertRaises((ValueError, ConnectionError)):
                execute_load(
                    conn, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=True
                )
            statements = [c.args[0] for c in cur.execute.call_args_list]
            self.assertEqual(sum(s.startswith("COPY INTO") for s in statements), 1)
            self.assertEqual("ROLLBACK" in statements, corrupt)
            self.assertEqual(statements.count("COMMIT"), int(commit_error))

    def test_disabled_auto_suspend_refuses_all_workload_sql(self):
        conn, cur = self.loader_connection(suspend=0)
        with self.assertRaisesRegex(ValueError, "cost controls"):
            execute_load(
                conn, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=True
            )
        self.assertEqual(cur.execute.call_count, 1)

    def test_account_monitor_is_verified_before_any_workload(self):
        for overrides in (
            {"level": "WAREHOUSE"},
            {"credit_quota": "0"},
            {"credit_quota": "NaN"},
            {"suspend_at": ""},
            {"suspend_immediately_at": "110%"},
            {"used_credits": "4.5"},
        ):
            with self.subTest(overrides=overrides):
                conn, cur = self.loader_connection(monitor_overrides=overrides)
                with self.assertRaisesRegex(ValueError, "monitor"):
                    execute_load(
                        conn,
                        manifest(),
                        "airline-bts-336805808138-us-east-2",
                        funding_verified=True,
                    )
                self.assertTrue(
                    all(c.args[0].startswith("SHOW ") for c in cur.execute.call_args_list)
                )
        conn, _ = self.loader_connection(monitor_visible=False)
        with self.assertRaisesRegex(ValueError, "monitor"):
            execute_load(
                conn, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=True
            )

    def test_live_account_monitor_shape_allows_immediate_only_protection(self):
        conn, _ = self.loader_connection(
            monitor_overrides={"suspend_at": None, "suspend_immediately_at": "100%"}
        )
        result = execute_load(
            conn, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=True
        )
        self.assertEqual(result["status"], "accepted")

    def test_plan_is_explicit_strict_and_keeps_full_source_schema(self):
        plan = build_load_plan(manifest(), "airline-bts-336805808138-us-east-2")
        self.assertEqual(
            plan["table"],
            "AIRLINE_DB.RAW.BTS_202501_" + manifest()["loaded_artifact_id"][:32].upper(),
        )
        self.assertEqual(plan["expected_rows"], 599013)
        self.assertIn("ON_ERROR = 'ABORT_STATEMENT'", plan["copy_sql"])
        self.assertIn("FORCE = FALSE", plan["copy_sql"])
        self.assertNotIn("PURGE = TRUE", plan["copy_sql"])
        self.assertIn('"Operating_Airline" VARCHAR', plan["create_sql"])
        self.assertIn('"SOURCE_ROW_NUMBER" NUMBER(38,0)', plan["create_sql"])
        self.assertIn("FILE_FORMAT", plan["copy_sql"])
        self.assertIn("MISMATCHED_FINGERPRINTS", plan["validation_sql"])
        self.assertIn("COUNT(DISTINCT", plan["validation_sql"])
        self.assertIn("prepared/", plan["object_key"])
        self.assertNotIn("CREATE OR REPLACE", plan["create_sql"])

    def test_rejects_untrusted_manifest_and_sql_paths(self):
        for update in [
            {"rows": 0},
            {"month": "2025-01'; DROP DATABASE AIRLINE_DB;--"},
            {"loaded_artifact_id": "not-a-hash"},
            {"prepared_columns": ["Wrong"]},
            {"source_kind": "unknown"},
        ]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                m = copy.deepcopy(manifest())
                m.update(update)
                build_load_plan(m, "airline-bts-336805808138-us-east-2")
        with self.assertRaises(ValueError):
            build_load_plan(manifest(), "foreign-bucket")

    def test_acceptance_checks_independent_counts_and_fingerprints(self):
        good = {
            "ROWS": 599013,
            "DISTINCT_ORDINALS": 599013,
            "FIRST_ORDINAL": 1,
            "LAST_ORDINAL": 599013,
            "WRONG_SOURCE": 0,
            "WRONG_MONTH": 0,
            "MISMATCHED_FINGERPRINTS": 0,
            "DEN_ROWS": 24732,
            "DEN_CANCELLED": 313,
            "DEN_DIVERTED": 69,
        }
        check_validation(good, manifest())
        for key in good:
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_validation({**good, key: good[key] + 1}, manifest())

    def test_load_refuses_unverified_funding_before_any_connection_access(self):
        with self.assertRaisesRegex(ValueError, "Funding"):
            execute_load(
                None, manifest(), "airline-bts-336805808138-us-east-2", funding_verified=False
            )

    def test_incomplete_validation_response_cannot_be_accepted(self):
        with self.assertRaises(ValueError):
            check_validation({}, manifest())
        good = {
            "ROWS": 599013,
            "DISTINCT_ORDINALS": 599013,
            "FIRST_ORDINAL": 1,
            "LAST_ORDINAL": 599013,
            "WRONG_MONTH": 0,
            "MISMATCHED_FINGERPRINTS": 0,
            "DEN_ROWS": 24732,
            "DEN_CANCELLED": 313,
            "DEN_DIVERTED": 69,
        }
        # Missing WRONG_SOURCE must not be interpreted as zero.
        with self.assertRaises(ValueError):
            check_validation(good, manifest())


if __name__ == "__main__":
    unittest.main()

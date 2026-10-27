"""Opt-in, funded Snowflake tests using only a <=10-row synthetic artifact.

No AWS credentials/uploads or production-table writes. See docs/ingestion.md for
fixture preparation/upload and the explicit environment switches. Default: skipped.
"""

import json
import os
import unittest
from pathlib import Path

from airline_warehouse.connection import connect
from airline_warehouse.load import build_load_plan, check_validation, execute_load, read_artifact


@unittest.skipUnless(
    os.environ.get("AIRLINE_LIVE_TESTS") == "funded-01-04"
    and os.environ.get("AIRLINE_TEST_ARTIFACT"),
    "Requires explicit funded opt-in and a staged synthetic fixture",
)
class LiveIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(os.environ["AIRLINE_TEST_ARTIFACT"])
        cls.manifest = read_artifact(cls.directory)
        if cls.manifest["source_kind"] != "synthetic-fixture" or cls.manifest["rows"] > 10:
            raise ValueError(
                "Live tests require an independently staged <=10-row synthetic fixture"
            )
        cls.plan = build_load_plan(cls.manifest, "airline-bts-336805808138-us-east-2")
        cls.connection = connect()
        cls.evidence = {
            "initial_fixture_load": execute_load(
                cls.connection, cls.manifest, cls.plan["bucket"], funding_verified=True
            )
        }

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()  # failure tables are TEMPORARY and disappear here
        (cls.directory.parent / "live-fixture-results.json").write_text(
            json.dumps(cls.evidence, indent=2, default=str) + "\n"
        )

    def test_01_fixture_replay_reuses_complete_population(self):
        result = execute_load(
            self.connection, self.manifest, self.plan["bucket"], funding_verified=True
        )
        self.assertEqual(result["status"], "reused")
        self.assertEqual(result["validation"]["ROWS"], self.manifest["rows"])
        self.evidence["fixture_replay"] = result

    def failure_case(self, name, files, *, wrong_month=False, wrong_format=False):
        from snowflake.connector.errors import DatabaseError

        table = self.plan["table"] + "_" + name.upper()
        relative = self.plan["object_key"].removeprefix("prepared/")
        # All interpolated paths are generated from validated SHA-256 identities.
        copy = self.plan["copy_sql"].replace(self.plan["table"], table, 1)
        copy = copy.replace(
            f"FILES = ('{relative}')", "FILES = (" + ", ".join(f"'{f}'" for f in files) + ")"
        )
        if wrong_format:
            copy = copy.replace(
                "FILE_FORMAT=(FORMAT_NAME='AIRLINE_DB.RAW.BTS_CSV_V1')",
                "FILE_FORMAT=(TYPE=CSV COMPRESSION=NONE SKIP_HEADER=1 "
                "ERROR_ON_COLUMN_COUNT_MISMATCH=TRUE)",
            )
        with self.connection.cursor() as cur:
            cur.execute(f"CREATE TEMPORARY TABLE {table} LIKE {self.plan['table']}")
            cur.execute("BEGIN")
            try:
                if wrong_month:
                    cur.execute(copy)
                    copy_id = cur.sfqid
                    cur.execute(self.plan["validation_sql"].replace(self.plan["table"], table))
                    row = dict(zip([c[0] for c in cur.description], cur.fetchone(), strict=True))
                    self.assertEqual(row["WRONG_MONTH"], self.manifest["rows"])
                    with self.assertRaises(ValueError):
                        check_validation(row, self.manifest)
                    self.evidence[name] = {"copy_query_id": copy_id, "validation": row}
                else:
                    # Missing fields can surface as IntegrityError (NOT NULL),
                    # while malformed encoding uses ProgrammingError. Both are
                    # DatabaseError subclasses; require a data/CSV diagnostic.
                    with self.assertRaises(DatabaseError) as caught:
                        cur.execute(copy)
                    message = caught.exception.msg.lower()
                    self.assertTrue(
                        any(term in message for term in ("column", "utf", "csv", "record")),
                        "Expected a data/CSV failure, not unrelated SQL or permission failure",
                    )
                    self.evidence[name] = {
                        "query_id": cur.sfqid,
                        "error_code": caught.exception.errno,
                        "sqlstate": caught.exception.sqlstate,
                    }
            finally:
                cur.execute("ROLLBACK")
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            remaining = cur.fetchone()[0]
            self.assertEqual(remaining, 0)
            self.evidence[name]["rows_after_rollback"] = remaining

    def test_02_malformed_copy_aborts_without_partial_rows(self):
        valid = self.plan["object_key"].removeprefix("prepared/")
        bad = f"tests/01-04/{self.manifest['loaded_artifact_id']}/malformed.csv.gz"
        self.failure_case("malformed", [valid, bad])

    def test_03_wrong_partition_is_rejected_and_copy_rolled_back(self):
        wrong = f"tests/01-04/{self.manifest['loaded_artifact_id']}/wrong-month.csv.gz"
        self.failure_case("wrong_month", [wrong], wrong_month=True)

    def test_04_wrong_file_format_fails_without_rows(self):
        valid = self.plan["object_key"].removeprefix("prepared/")
        self.failure_case("wrong_format", [valid], wrong_format=True)

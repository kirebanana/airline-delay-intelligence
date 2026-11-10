import datetime as dt
import unittest
from unittest.mock import MagicMock

from airline_warehouse.analytics import Filters, cache_identity, filter_options, query_weather


class AnalyticalRequestTests(unittest.TestCase):
    def test_airport_locations_use_only_the_validated_release_dimension(self):
        for development, prefix, dimension in [
            (False, "RELEASE", "AIRPORTS"),
            (True, "WORK", "DIM_AIRPORT"),
        ]:
            connection = MagicMock()
            cur = connection.cursor.return_value.__enter__.return_value
            cur.fetchone.return_value = (dt.date(2025, 1, 1), dt.date(2025, 1, 31))
            cur.fetchall.side_effect = [
                [(19393, "WN")],
                [(11292, "DEN")],
                [(11292, "DEN", "Denver, CO")],
            ]
            schema = prefix + "_" + "A" * 24
            options = filter_options(
                connection, {"sealed": True, "schema": schema}, development=development
            )
            self.assertEqual(options["airport_locations"], [(11292, "DEN", "Denver, CO")])
            self.assertEqual(
                cur.execute.call_args.args[0],
                f"SELECT airport_id,airport_code,city FROM AIRLINE_DB.{schema}.{dimension} "
                "ORDER BY airport_id LIMIT 1000",
            )

    def test_weather_core_does_not_query_collapsed_diagnostics(self):
        class Connection:
            description = [("X",)]

            def __init__(self):
                self.sql = []

            def cursor(self):
                return self

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, sql, parameters):
                self.sql.append(sql)

            def fetchall(self):
                return []

        c = Connection()
        descriptor = {"sealed": True, "schema": "RELEASE_" + "A" * 24, "weather": True}
        filters = Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31), origin=11292)
        core = query_weather(c, descriptor, filters, details=False)
        self.assertEqual(len(c.sql), 6)
        self.assertEqual(core["daily"], [])
        self.assertEqual(core["pilot_coverage"], [])
        self.assertTrue(any("'ambiguous_local_time'" in sql for sql in c.sql))
        self.assertTrue(any("'nonexistent_local_time'" in sql for sql in c.sql))
        c.sql.clear()
        query_weather(c, descriptor, filters, details=True)
        self.assertEqual(len(c.sql), 12)

    def test_cache_isolated_by_target_release_every_filter_and_ranking_threshold(self):
        descriptor = {
            "schema": "RELEASE_" + "A" * 24,
            "target": "january",
            "release_id": "a" * 32,
            "processing_contract": "v1",
        }
        base = Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31))
        key = cache_identity(descriptor, base, "carrier", 100, 500)
        self.assertNotEqual(
            key, cache_identity({**descriptor, "target": "test"}, base, "carrier", 100, 500)
        )
        self.assertNotEqual(
            key, cache_identity({**descriptor, "release_id": "b" * 32}, base, "carrier", 100, 500)
        )
        self.assertNotEqual(key, cache_identity(descriptor, base, "carrier", 99, 500))
        self.assertNotEqual(
            key,
            cache_identity(
                descriptor, Filters(base.start, base.end, origin=11292), "carrier", 100, 500
            ),
        )
        with self.assertRaises(ValueError):
            Filters(base.start, base.end, origin="DEN'; DROP TABLE X;--")

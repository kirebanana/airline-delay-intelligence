import datetime as dt
import unittest

from airline_warehouse.analytics import Filters, cache_identity


class AnalyticalRequestTests(unittest.TestCase):
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

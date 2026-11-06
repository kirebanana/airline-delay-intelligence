import datetime as dt
import unittest

from airline_warehouse.analytics import Filters
from airline_warehouse.dashboard_views import (
    comparison_table,
    group_label,
    ordered_rows,
    prior_year,
    weather_support,
)


class PresentationTests(unittest.TestCase):
    def test_comparison_cells_keep_numeric_sorting_and_missing_quantiles(self):
        row = {
            "MARKETING_LABEL": "UA",
            "SCHEDULED_ROWS": 260,
            "ARRIVAL_RATE": 178 / 258,
            "CANCELLATION_RATE": 2 / 260,
            "DIVERSION_RATE": 0,
            "DEPARTURE_RATE": 69 / 258,
            "SIGNED_MEDIAN": -2,
            "SIGNED_P90": None,
            "ARRIVAL_DENOMINATOR": 258,
            "DEPARTURE_DENOMINATOR": 258,
            "SIGNED_ARRIVAL_COUNT": 258,
        }
        shown = comparison_table([row], "carrier")[0]
        self.assertEqual(shown["Scheduled"], 260)
        self.assertAlmostEqual(shown["On-time"], 100 * 178 / 258)
        self.assertEqual(shown["Median min"], -2)
        self.assertIsNone(shown["p90 min"])

    def test_hours_keep_numeric_order_and_source_midnight(self):
        rows = [{"SCHEDULED_LOCAL_HOUR": h} for h in [24, 2, 10, 0, 1, 23]]
        ordered = ordered_rows(rows, "hour")
        self.assertEqual([r["SCHEDULED_LOCAL_HOUR"] for r in ordered], [0, 1, 2, 10, 23, 24])
        self.assertEqual(
            [group_label(r, "hour") for r in ordered],
            ["00:00", "01:00", "02:00", "10:00", "23:00", "Source 2400"],
        )

    def test_weather_support_uses_each_metric_population(self):
        self.assertEqual(
            weather_support(
                {"LOCAL_DATES": 5, "SCHEDULED_ROWS": 120, "DEPARTURE_DENOMINATOR": 80}, 100
            ),
            (True, True, False),
        )

    def test_equivalent_period_preserves_filters_and_clamps_leap_day(self):
        f = Filters(dt.date(2024, 2, 1), dt.date(2024, 2, 29), (19977,), 11292, 13930)
        p = prior_year(f, dt.date(2023, 1, 1), dt.date(2025, 12, 31))
        self.assertEqual(
            p, Filters(dt.date(2023, 2, 1), dt.date(2023, 2, 28), (19977,), 11292, 13930)
        )
        self.assertIsNone(prior_year(p, dt.date(2023, 1, 1), dt.date(2025, 12, 31)))

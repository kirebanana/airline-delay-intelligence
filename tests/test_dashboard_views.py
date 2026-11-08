import datetime as dt
import unittest

from airline_warehouse.analytics import Filters
from airline_warehouse.dashboard_views import (
    WEATHER_BANDS,
    arrival_timing,
    comparison_table,
    group_label,
    ordered_rows,
    percent_value,
    prior_year,
    sort_comparisons,
    weather_scope,
    weather_support,
)


class PresentationTests(unittest.TestCase):
    def test_order_is_metric_based_and_missing_or_small_samples_are_last(self):
        rows = [
            {
                "MARKETING_LABEL": name,
                "SCHEDULED_ROWS": count,
                "ARRIVAL_RATE": rate,
                "ARRIVAL_DENOMINATOR": den,
            }
            for name, count, rate, den in [
                ("AA", 500, 0.5, 500),
                ("BB", 200, 0.9, 200),
                ("CC", 2, 1.0, 2),
                ("DD", 100, None, 0),
            ]
        ]

        def order(choice):
            return [
                r["MARKETING_LABEL"]
                for r in sort_comparisons(
                    rows, "carrier", "ARRIVAL_RATE", "ARRIVAL_DENOMINATOR", 100, choice
                )
            ]

        self.assertEqual(order("Highest rate first"), ["BB", "AA", "CC", "DD"])
        self.assertEqual(order("Lowest rate first"), ["AA", "BB", "CC", "DD"])
        self.assertEqual(order("Most flights"), ["AA", "BB", "DD", "CC"])
        self.assertEqual(arrival_timing(-6), "6.0 min early")
        self.assertEqual(arrival_timing(44), "44.0 min late")
        self.assertEqual(arrival_timing(None), "N/A")

    def test_weather_scope_requires_pilot_origin_and_contained_dates(self):
        base = Filters(dt.date(2025, 1, 1), dt.date(2025, 1, 31))
        from dataclasses import replace

        self.assertFalse(weather_scope(base))
        self.assertTrue(weather_scope(replace(base, origin=11292)))
        self.assertFalse(weather_scope(replace(base, origin=11292, end=dt.date(2025, 2, 1))))
        self.assertEqual(WEATHER_BANDS["wind"], ["<5 m/s", "5–<10 m/s", "≥10 m/s", "Unmatched"])
        self.assertIsNone(percent_value(None))
        self.assertEqual(percent_value(0.06), 6.0)

    def test_horizontal_axis_disables_label_suppression(self):
        from unittest.mock import patch

        from airline_warehouse.dashboard import plot

        with patch("airline_warehouse.dashboard.st.altair_chart") as draw:
            plot([{"Group": str(i), "Rate": 0.5} for i in range(10)], "Group", "Rate", rate=True)
        spec = draw.call_args.args[0].to_dict()
        self.assertFalse(spec["encoding"]["y"]["axis"]["labelOverlap"])
        self.assertGreaterEqual(spec["height"], 320)

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

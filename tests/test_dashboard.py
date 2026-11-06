import datetime as dt
import importlib.util
import unittest

if importlib.util.find_spec("streamlit"):
    from streamlit.testing.v1 import AppTest

else:
    AppTest = None


def render(reader):
    from airline_warehouse.dashboard import render as dashboard

    dashboard(reader)


class FixtureReader:
    """External analytical-read boundary, not a second production metric engine."""

    def pin(self):
        return {
            "schema": "WORK_" + "F" * 24,
            "processing_contract": "ui-fixture-v1",
            "sealed": True,
            "development": True,
            "target": "test",
            "built_at": "2025-02-01",
        }

    def validate(self, descriptor):
        return None

    def secondary(self, descriptor, filters):
        return {
            "summary": {
                "SCHEDULED_ROWS": 10,
                "CATEGORY_ELIGIBLE": 4,
                "CATEGORY_COMPLETE": 3,
                "MISSING_CATEGORY_ROWS": 1,
                "EXCLUDED_ARRIVAL_MINUTES": 20,
                "ALLOCATION_MISMATCH_ROWS": 1,
                "UNALLOCATED_MINUTES": 1345,
                "RECOVERY_ELIGIBLE": 3,
                "RECOVERED": 1,
                "RECOVERY_SHARE": 1 / 3,
                "IMPROVEMENT_MEAN": 7,
                "IMPROVEMENT_MEDIAN": 6,
                "IMPROVEMENT_P90": 13.2,
            },
            "categories": [],
            "cancellations": [],
            "distribution": [],
        }

    def options(self, descriptor):
        return {
            "start": dt.date(2025, 1, 1),
            "end": dt.date(2025, 1, 2),
            "carriers": [(19393, "WN")],
            "airports": [(11292, "DEN"), (14771, "SFO")],
        }

    def metrics(self, descriptor, filters, group, minimum):
        if group != "all":
            return []
        empty = filters.origin == 14771
        return [
            {
                "SCHEDULED_ROWS": 0 if empty else 10,
                "ARRIVAL_RATE": None if empty else 0.6,
                "CANCELLATION_RATE": None if empty else 0.1,
                "DIVERSION_RATE": None if empty else 0,
                "DEPARTURE_RATE": None if empty else 0.25,
                "ARRIVAL_NUMERATOR": 0 if empty else 3,
                "ARRIVAL_DENOMINATOR": 0 if empty else 5,
                "CANCELLATION_NUMERATOR": 0 if empty else 1,
                "DIVERSION_NUMERATOR": 0,
                "DEPARTURE_NUMERATOR": 0 if empty else 2,
                "DEPARTURE_DENOMINATOR": 0 if empty else 8,
                "SIGNED_ARRIVAL_COUNT": 0 if empty else 5,
                "SIGNED_MEAN": None if empty else 15.8,
                "SIGNED_MEDIAN": None if empty else 14,
                "SIGNED_P90": None if empty else 42,
                "UNKNOWN_CANCELLED": 0,
                "UNKNOWN_DIVERTED": 0,
                "UNKNOWN_ARRIVAL": 0,
                "UNKNOWN_DEPARTURE": 0,
            }
        ]


@unittest.skipUnless(AppTest is not None, "Install the pinned analytics extra for AppTest")
class DashboardTests(unittest.TestCase):
    def test_secondary_values_sort_numerically_and_threshold_reuses_results(self):
        class NumericReader(FixtureReader):
            calls = 0

            def pin(self):
                return {**super().pin(), "processing_contract": "numeric-sort-fixture"}

            def secondary(self, descriptor, filters):
                self.calls += 1
                result = super().secondary(descriptor, filters)
                result["categories"] = [
                    {
                        "CATEGORY": str(i),
                        "MINUTE_SHARE": value,
                        "REPORTED_MINUTES": i * 100,
                        "AFFECTED_RATE": value,
                    }
                    for i, value in enumerate([0.002, 0.195, 0.339, 0.404, 0.06])
                ]
                return result

        reader = NumericReader()
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("Disruption & recovery").run()
        frame = next(d.value for d in app.dataframe if "Minute share" in d.value.columns)
        self.assertEqual(
            list(frame.sort_values("Minute share")["Minute share"].round(1)),
            [0.2, 6.0, 19.5, 33.9, 40.4],
        )
        app.number_input(key="minimum").set_value(800).run()
        self.assertFalse(app.error)
        self.assertEqual(reader.calls, 1)

    def test_fixed_weather_scope_coverage_and_empty_non_den_filters(self):
        class WeatherReader(FixtureReader):
            def pin(self):
                return {**super().pin(), "weather": {"weather_id": "fixture-only"}}

            def weather(self, descriptor, filters, *, details=True):
                return {
                    "pilot_coverage": [
                        {"VARIABLE": "temperature", "SCHEDULED_ROWS": 10, "MATCHED_ROWS": 10}
                    ],
                    "selected_coverage": [],
                    "daily": [],
                    "comparisons": []
                    if filters.origin == 14771
                    else [
                        {
                            "VARIABLE": "temperature",
                            "BAND": "cold",
                            "LOCAL_DATES": 1,
                            "SCHEDULED_ROWS": 10,
                            "DEPARTURE_DENOMINATOR": 8,
                            "DEPARTURE_DELAY_RATE": 0.25,
                            "CANCELLATION_RATE": 0.1,
                            "LARGEST_DATE_SHARE": 1,
                        }
                    ],
                }

        app = AppTest.from_function(render, args=(WeatherReader(),)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("outside the weather pilot" in w.value for w in app.warning))
        app.selectbox(key="origin").set_value(11292).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("five local dates" in w.value for w in app.warning))
        app.selectbox(key="origin").set_value(14771).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("outside the weather pilot" in w.value for w in app.warning))

    def test_categories_and_recovery_explain_populations_without_causal_claims(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        app.radio(key="task").set_value("Disruption & recovery").run()
        self.assertFalse(app.exception)
        headings = [h.value for h in app.subheader]
        self.assertIn("Reported delay categories", headings)
        self.assertIn("Schedule-relative recovery", headings)
        self.assertTrue(any("1,345" in str(w.value) for w in app.warning))
        self.assertTrue(
            any("20" in str(w.value) and "Excluded" in str(w.value) for w in app.markdown)
        )

    def test_expired_token_stops_before_cached_results_without_fallback(self):
        class ExpiredReader(FixtureReader):
            def __init__(self):
                self.checks = 0

            def validate(self, descriptor):
                self.checks += 1
                if self.checks >= 2:
                    raise ValueError("Expired token")

        app = AppTest.from_function(render, args=(ExpiredReader(),)).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("Reload" in message.value for message in app.error))

    def test_filters_empty_and_reset_preserve_explicit_development_scope(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("UNPUBLISHED" in w.value for w in app.warning))
        self.assertEqual(app.metric[0].value, "60.0%")
        self.assertIsNone(app.selectbox(key="origin").value)
        self.assertEqual(app.multiselect(key="carriers").value, [])
        app.selectbox(key="destination").set_value(11292).run()
        self.assertIsNone(app.selectbox(key="origin").value)
        app.selectbox(key="origin").set_value(14771).run()
        app.multiselect(key="carriers").set_value([19393]).run()
        app.number_input(key="minimum").set_value(200).run()
        app.button(key="reset").click().run()
        self.assertIsNone(app.selectbox(key="origin").value)
        self.assertIsNone(app.selectbox(key="destination").value)
        self.assertEqual(app.multiselect(key="carriers").value, [])
        self.assertEqual(app.number_input(key="minimum").value, 100)
        self.assertEqual(app.metric[0].value, "60.0%")
        app.selectbox(key="destination").set_value(11292).run()
        self.assertIsNone(app.selectbox(key="origin").value)

    def test_route_swap_and_prior_year_unavailable_are_safe(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        app.radio(key="task").set_value("Time & routes").run()
        app.selectbox(key="origin").set_value(11292).run()
        app.selectbox(key="destination").set_value(14771).run()
        next(b for b in app.button if b.label == "Reverse route").click().run()
        self.assertEqual(app.selectbox(key="origin").value, 14771)
        self.assertEqual(app.selectbox(key="destination").value, 11292)
        self.assertFalse(app.error)
        self.assertTrue(app.checkbox[0].disabled)

    def test_unrelated_sections_are_not_queried(self):
        class CountingReader(FixtureReader):
            def secondary(self, *args):
                raise AssertionError("Network task must not query secondary")

            def weather(self, *args):
                raise AssertionError("Network task must not query weather")

        app = AppTest.from_function(render, args=(CountingReader(),)).run()
        self.assertFalse(app.error)
        self.assertFalse(app.exception)
        app.selectbox(key="origin").set_value(14771).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "N/A")
        app.button(key="reset").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "60.0%")

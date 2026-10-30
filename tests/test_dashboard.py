import datetime as dt
import importlib.util
import unittest

if importlib.util.find_spec("streamlit"):
    from streamlit.testing.v1 import AppTest

    from airline_warehouse.dashboard import render
else:
    AppTest = None


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
    def test_categories_and_recovery_explain_populations_without_causal_claims(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        self.assertFalse(app.exception)
        headings = [h.value for h in app.subheader]
        self.assertIn("Reported delay categories", headings)
        self.assertIn("Schedule-relative recovery", headings)
        self.assertTrue(any("1345" in str(w.value) for w in app.warning))

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
        app.selectbox(key="origin").set_value(14771).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "N/A")
        app.button(key="reset").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "60.0%")

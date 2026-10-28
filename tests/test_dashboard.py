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

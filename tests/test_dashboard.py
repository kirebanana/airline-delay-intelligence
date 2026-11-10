import datetime as dt
import importlib.util
import json
import unittest

if importlib.util.find_spec("streamlit"):
    from streamlit.testing.v1 import AppTest

else:
    AppTest = None

LEGACY_WEATHER = {
    "weather_id": "fixture-only",
    "contract": "den-isd-aviation-qc15-independent-60m-v1",
    "origin_id": 11292,
    "station": "72565003017",
    "start": "2025-01-01T06:00:00+00:00",
    "end": "2025-02-01T07:00:00+00:00",
}
FULL_PERIOD_WEATHER = {
    "weather_id": "full-period-fixture-only",
    "contract": "den-ghcnh-aviation-independent-60m-v2",
    "origin_id": 11292,
    "station": "USW00003017",
    "scope_start": "2023-01-01",
    "scope_end_exclusive": "2026-01-01",
}


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
            "airport_locations": [
                (11292, "DEN", "Denver, CO"),
                (14771, "SFO", "San Francisco, CA"),
            ],
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


class ReleasedWeatherReader(FixtureReader):
    def __init__(self, manifest=None):
        self.manifest = FULL_PERIOD_WEATHER if manifest is None else manifest
        self.weather_filters = []

    def pin(self):
        return {
            **super().pin(),
            "development": False,
            "release_id": "offline-ui-fixture",
            "weather": self.manifest,
        }

    def options(self, descriptor):
        return {
            **super().options(descriptor),
            "start": dt.date(2023, 1, 1),
            "end": dt.date(2025, 12, 31),
        }

    def weather(self, descriptor, filters, *, details=True):
        assert not details, "Dashboard must not request raw weather diagnostics"
        self.weather_filters.append(filters)
        return {
            "selected_coverage": [
                {"VARIABLE": variable, "SCHEDULED_ROWS": 10, "MATCHED_ROWS": 8}
                for variable in ("temperature", "wind", "visibility")
            ],
            "comparisons": [
                {
                    "VARIABLE": "temperature",
                    "BAND": "Unmatched",
                    "LOCAL_DATES": 1,
                    "SCHEDULED_ROWS": 10,
                    "DEPARTURE_DENOMINATOR": 8,
                    "DEPARTURE_DELAY_RATE": 0.25,
                    "CANCELLATION_RATE": 0.1,
                    "LARGEST_DATE_SHARE": 1,
                }
            ],
        }


@unittest.skipUnless(AppTest is not None, "Install the pinned analytics extra for AppTest")
class DashboardTests(unittest.TestCase):
    def test_routes_are_visible_default_and_no_technical_expanders_remain(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        self.assertEqual(len(app.expander), 0)
        app.radio(key="task").set_value("Time & routes").run()
        self.assertEqual(app.radio(key="group").value, "route")
        self.assertIn("Routes", app.radio(key="group").options)
        self.assertIn("Compare routes", [h.value for h in app.subheader])
        self.assertEqual(len(app.expander), 0)
        app.selectbox(key="origin").set_value(11292).run()
        app.selectbox(key="destination").set_value(14771).run()
        self.assertFalse(app.exception)
        self.assertIn(
            "Both route directions · same dates and airlines", [h.value for h in app.subheader]
        )
        self.assertNotIn("Compare routes", [h.value for h in app.subheader])
        app.radio(key="group").set_value("hour").run()
        self.assertNotIn(
            "Both route directions · same dates and airlines", [h.value for h in app.subheader]
        )

    def test_homepage_shows_all_airlines_with_metric_order_and_no_technical_dump(self):
        class AirlineReader(FixtureReader):
            def pin(self):
                return {**super().pin(), "processing_contract": "all-airlines-sort-fixture"}

            def metrics(self, descriptor, filters, group, minimum):
                base = super().metrics(descriptor, filters, "all", minimum)[0]
                if group == "carrier":
                    return [
                        {
                            **base,
                            "MARKETING_LABEL": f"C{i:02}",
                            "MARKETING_CARRIER_ID": 1000 + i,
                            "ARRIVAL_RATE": i / 20,
                            "ARRIVAL_DENOMINATOR": 500,
                        }
                        for i in range(11)
                    ]
                return [base] if group == "all" else []

        app = AppTest.from_function(render, args=(AirlineReader(),)).run()
        self.assertFalse(app.error)
        self.assertEqual(len(app.slider), 0)
        frame = next(d.value for d in app.dataframe if "Airline" in d.value.columns)
        self.assertEqual(len(frame), 11)
        self.assertEqual(frame.iloc[0]["Airline"], "C10")
        app.selectbox(key="order_carrier").set_value("Lowest rate first").run()
        frame = next(d.value for d in app.dataframe if "Airline" in d.value.columns)
        self.assertEqual(frame.iloc[0]["Airline"], "C00")
        self.assertEqual(len([d for d in app.dataframe if "On-time" in d.value.columns]), 1)
        self.assertNotIn("Full comparison table and flight counts", [e.label for e in app.expander])
        self.assertIn("Southwest Airlines (WN)", app.multiselect(key="carriers").options)
        self.assertEqual(len(app.json), 0)
        self.assertFalse(any("Signed arrival delay ·" in m.value for m in app.markdown))
        self.assertTrue(
            any('[data-testid="stCaptionContainer"] {opacity:1;' in m.value for m in app.markdown)
        )

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
                return {**super().pin(), "weather": LEGACY_WEATHER}

            def weather(self, descriptor, filters, *, details=True):
                if details:
                    raise AssertionError("Dashboard must not request raw weather diagnostics")
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
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))
        app.selectbox(key="origin").set_value(11292).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("only 2 days" in w.value for w in app.warning))
        self.assertEqual(len(app.expander), 0)
        self.assertEqual(len(app.checkbox), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertNotIn("Selection overview", [h.value for h in app.subheader])
        self.assertTrue(any("10 scheduled flights" in m.value for m in app.markdown))
        next(s for s in app.selectbox if s.label == "Weather variable").set_value("wind").run()
        self.assertFalse(app.error)
        self.assertEqual(len(app.metric), 0)
        app.selectbox(key="origin").set_value(14771).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))

    def test_released_full_period_weather_alignment_narrowing_and_reset(self):
        reader = ReleasedWeatherReader()
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        self.assertEqual(reader.weather_filters, [])
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))
        next(b for b in app.button if b.label == "Align filters to DEN · 2023–2025").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(
            app.date_input(key="dates").value, (dt.date(2023, 1, 1), dt.date(2025, 12, 31))
        )
        self.assertEqual(app.selectbox(key="origin").value, 11292)
        self.assertFalse(any("UNPUBLISHED" in w.value for w in app.warning))
        self.assertEqual(len(app.metric), 0)
        self.assertEqual(len(app.expander), 0)
        self.assertEqual(len(app.get("vega_lite_chart")), 0)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(
            list(app.dataframe[0].value.columns),
            ["Band", "Departure delayed", "Cancelled", "Scheduled", "Dates", "Support"],
        )
        self.assertTrue(
            any(
                "Weather matched for 80.0%" in c.value and "2 without a match" in c.value
                for c in app.caption
            )
        )
        self.assertTrue(any("10 scheduled flights" in m.value for m in app.markdown))
        self.assertIn("TRAVEL DATES", [c.value for c in app.caption])
        app.date_input(key="dates").set_value((dt.date(2024, 2, 28), dt.date(2024, 2, 29))).run()
        app.multiselect(key="carriers").set_value([19393]).run()
        app.selectbox(key="destination").set_value(14771).run()
        self.assertEqual(reader.weather_filters[-1].start, dt.date(2024, 2, 28))
        self.assertEqual(reader.weather_filters[-1].end, dt.date(2024, 2, 29))
        self.assertEqual(reader.weather_filters[-1].carriers, (19393,))
        self.assertEqual(reader.weather_filters[-1].destination, 14771)
        warnings = " ".join(w.value for w in app.warning)
        self.assertIn("only 2 days", warnings)
        self.assertNotIn("January", warnings)
        self.assertTrue(any("not proof" in c.value for c in app.caption))
        app.button(key="reset").click().run()
        self.assertIsNone(app.selectbox(key="origin").value)
        self.assertIsNone(app.selectbox(key="destination").value)
        self.assertEqual(app.multiselect(key="carriers").value, [])
        self.assertEqual(
            app.date_input(key="dates").value, (dt.date(2023, 1, 1), dt.date(2025, 12, 31))
        )
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))
        app.radio(key="task").set_value("Time & routes").run()
        self.assertEqual(app.radio(key="group").value, "route")

    def test_legacy_release_alignment_stays_january_despite_full_flight_dates(self):
        reader = ReleasedWeatherReader(LEGACY_WEATHER)
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        next(b for b in app.button if b.label == "Use DEN · January 2025").click().run()
        self.assertFalse(app.error)
        self.assertEqual(
            app.date_input(key="dates").value, (dt.date(2025, 1, 1), dt.date(2025, 1, 31))
        )
        calls = len(reader.weather_filters)
        app.selectbox(key="period").set_value("2024").run()
        self.assertEqual(len(reader.weather_filters), calls)
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))
        self.assertEqual(len(app.dataframe), 0)

    def test_unsupported_weather_metadata_has_no_alignment_or_weather_queries(self):
        for manifest in [
            {},
            {"weather_id": "fixture-only"},
            {**FULL_PERIOD_WEATHER, "contract": "unknown"},
            {**FULL_PERIOD_WEATHER, "scope_start": "not-a-date"},
            {**FULL_PERIOD_WEATHER, "scope_end_exclusive": "2027-01-01"},
            {k: v for k, v in FULL_PERIOD_WEATHER.items() if k != "scope_start"},
        ]:
            with self.subTest(manifest=manifest):
                reader = ReleasedWeatherReader(manifest)
                app = AppTest.from_function(render, args=(reader,)).run()
                app.radio(key="task").set_value("DEN weather investigation").run()
                app.selectbox(key="origin").set_value(11292).run()
                self.assertFalse(app.exception)
                self.assertTrue(any("no supported weather scope" in w.value for w in app.warning))
                self.assertFalse(any("DEN ·" in b.label for b in app.button))
                self.assertEqual(reader.weather_filters, [])
                self.assertEqual(len(app.dataframe), 0)

    def test_alignment_uses_narrower_released_weather_not_all_flight_dates(self):
        reader = ReleasedWeatherReader(
            {
                **FULL_PERIOD_WEATHER,
                "scope_start": "2024-02-01",
                "scope_end_exclusive": "2024-03-01",
            }
        )
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        next(b for b in app.button if b.label == "Use DEN · February 2024").click().run()
        self.assertFalse(app.error)
        self.assertEqual(
            app.date_input(key="dates").value, (dt.date(2024, 2, 1), dt.date(2024, 2, 29))
        )
        calls = len(reader.weather_filters)
        app.selectbox(key="period").set_value("All years").run()
        self.assertEqual(len(reader.weather_filters), calls)
        self.assertTrue(any("outside this weather study" in w.value for w in app.warning))

    def test_weather_alignment_intersects_flight_coverage_and_requires_den(self):
        class ShortFlightReader(ReleasedWeatherReader):
            def pin(self):
                return {**super().pin(), "release_id": "short-flight-ui-fixture"}

            def options(self, descriptor):
                return {
                    **super().options(descriptor),
                    "start": dt.date(2024, 6, 1),
                    "end": dt.date(2024, 6, 2),
                }

        reader = ShortFlightReader()
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        next(b for b in app.button if b.label.startswith("Use DEN ·")).click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(
            app.date_input(key="dates").value, (dt.date(2024, 6, 1), dt.date(2024, 6, 2))
        )
        self.assertTrue(any("only 2 days" in w.value for w in app.warning))

        class NonDenReader(ReleasedWeatherReader):
            def pin(self):
                return {**super().pin(), "release_id": "non-den-ui-fixture"}

            def options(self, descriptor):
                return {**super().options(descriptor), "airports": [(14771, "SFO")]}

        reader = NonDenReader()
        app = AppTest.from_function(render, args=(reader,)).run()
        app.radio(key="task").set_value("DEN weather investigation").run()
        self.assertFalse(app.exception)
        self.assertFalse(any("DEN ·" in b.label for b in app.button))
        self.assertEqual(reader.weather_filters, [])

    def test_categories_and_recovery_explain_populations_without_causal_claims(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        app.radio(key="task").set_value("Disruption & recovery").run()
        self.assertFalse(app.exception)
        headings = [h.value for h in app.subheader]
        self.assertIn("What types of delay were reported?", headings)
        self.assertIn("Did flights make up time after a late departure?", headings)
        self.assertEqual(len(app.expander), 0)
        self.assertNotIn("Selection overview", headings)
        self.assertNotIn("On-time arrivals", [m.label for m in app.metric])
        self.assertIn(
            "Late departures that arrived less than 15 minutes late", [m.label for m in app.metric]
        )
        self.assertTrue(any("10 scheduled flights" in m.value for m in app.markdown))
        captions = " ".join(w.value for w in app.caption)
        self.assertNotIn("Data gaps:", captions)
        self.assertNotIn("1,345", captions)
        self.assertNotIn("Missing flight status:", captions)
        self.assertIn("at least 15 minutes late", captions)
        self.assertIn("does not always mean arriving on time", captions)

    def test_selection_overview_and_named_directional_routes(self):
        app = AppTest.from_function(render, args=(FixtureReader(),)).run()
        self.assertIn("Selection overview", [h.value for h in app.subheader])
        self.assertIn("On-time arrivals", [m.label for m in app.metric])
        self.assertIn("All routes", [m.value for m in app.markdown])
        self.assertIn("Denver, CO (DEN)", app.selectbox(key="origin").options)
        app.radio(key="task").set_value("Time & routes").run()
        self.assertNotIn("Selection overview", [h.value for h in app.subheader])
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("10 scheduled flights" in m.value for m in app.markdown))
        app.selectbox(key="origin").set_value(11292).run()
        app.selectbox(key="destination").set_value(14771).run()
        self.assertFalse(app.exception)
        frame = next(d.value for d in app.dataframe if "Group" in d.value.columns)
        self.assertEqual(frame.iloc[0]["Group"], "Denver, CO (DEN) → San Francisco, CA (SFO)")

    def test_route_ranking_table_has_locations_and_chart_has_location_tooltip(self):
        class RouteReader(FixtureReader):
            def metrics(self, descriptor, filters, group, minimum):
                if group == "route":
                    return [
                        {
                            **super().metrics(descriptor, filters, "all", minimum)[0],
                            "ORIGIN_ID": 11292,
                            "ORIGIN_LABEL": "DEN",
                            "DESTINATION_ID": 14771,
                            "DESTINATION_LABEL": "SFO",
                        }
                    ]
                return super().metrics(descriptor, filters, group, minimum)

        app = AppTest.from_function(render, args=(RouteReader(),)).run()
        app.number_input(key="minimum").set_value(1).run()
        app.radio(key="task").set_value("Time & routes").run()
        self.assertFalse(app.exception)
        frame = next(d.value for d in app.dataframe if "Route" in d.value.columns)
        self.assertEqual(frame.iloc[0]["Route"], "Denver, CO (DEN) → San Francisco, CA (SFO)")
        chart = app.get("vega_lite_chart")[0]
        spec = json.loads(chart.proto.spec)
        self.assertIn({"field": "Location", "type": "nominal"}, spec["encoding"]["tooltip"])

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
        self.assertTrue(any("reload" in message.value.lower() for message in app.error))

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

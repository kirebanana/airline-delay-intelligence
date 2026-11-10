"""Offline artifact/replay, timezone and independent matching contract boundaries."""

import datetime as dt
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from airline_warehouse.ghcnh import BASE_URL, SOURCE_SIZES
from airline_warehouse.weather import (
    GHCNH_CONTRACT,
    classified_anchor,
    load_weather,
    observation_index,
    oracle_match,
    read_weather,
    render_weather_sql,
    validate_frozen_weather,
    validate_weather_inputs,
    weather_limits,
    weather_variables,
)
from airline_warehouse.weather_contract import mapping_sha256, reference


def manifest():
    ref = reference()
    result = {
        key: ref[key]
        for key in (
            "scope_start",
            "scope_end_exclusive",
            "start",
            "end",
            "station",
            "origin_id",
            "timezone",
            "timezone_sha256",
            "origin_sequences",
        )
    }
    result.update(
        contract=GHCNH_CONTRACT,
        mapping_version=ref["version"],
        mapping_sha256=mapping_sha256(),
        sources=[
            {
                "year": y,
                "sha256": ref["source_objects"][str(y)]["sha256"],
                "validators": {
                    k: v for k, v in ref["source_objects"][str(y)].items() if k != "sha256"
                },
                "bytes": SOURCE_SIZES[y],
                "kind": "initial_byte_range" if y == 2026 else "annual_psv",
                "url": f"{BASE_URL}/{y}/psv/GHCNh_USW00003017_{y}.psv",
            }
            for y in range(2023, 2027)
        ],
    )
    return result


def record(variable, stamp, value, status="accepted"):
    return dict(
        station="USW00003017",
        observed_at=stamp,
        variable=variable,
        value=value,
        status=status,
        duplicate_count=1,
        provenance=[{"source_sha256": "a" * 64, "source_row": 1}],
    )


LIMITS = {
    "AIRLINE_WEATHER_MAX_BYTES": "100000",
    "AIRLINE_WEATHER_MAX_OBSERVATIONS": "20",
    "AIRLINE_WEATHER_MAX_FLIGHTS": "930445",
}


class ReplayConnection:
    """Stateful input boundary: existing raw table is never overwritten on replay."""

    def __init__(self):
        self.rows = []
        self.statements = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.statements.append(sql)
        if sql.startswith("INSERT INTO"):
            self.rows.extend(params)
        elif not sql.startswith(
            ("SELECT record FROM", "CREATE TRANSIENT TABLE", "BEGIN", "COMMIT")
        ):
            raise AssertionError(sql)

    def fetchall(self):
        return [(row,) for row in self.rows]


class WeatherReleaseTests(unittest.TestCase):
    def test_insert_batches_have_record_and_payload_bounds(self):
        for rows, expected in [(["x"] * 4001, 3), (["x" * 600000] * 7, 3)]:
            data = {"contract": GHCNH_CONTRACT, "weather_id": "a" * 64}
            connection = ReplayConnection()
            with (
                patch("airline_warehouse.weather.read_weather", return_value=(data, rows)),
                patch.dict(os.environ, {**LIMITS, "AIRLINE_WEATHER_MAX_OBSERVATIONS": "5000"}),
            ):
                load_weather(connection, Path("unused"))
            inserts = [s for s in connection.statements if s.startswith("INSERT INTO")]
            self.assertEqual(len(inserts), expected)
            self.assertEqual(connection.rows, rows)

    def write_artifact(self, path):
        rows = [
            record(v, "2023-01-01T06:00:00+00:00", 1) for v in ("temperature", "visibility", "wind")
        ]
        for row in rows:
            row["provenance"] = [
                dict(
                    value=1,
                    status="accepted",
                    raw="0.001" if row["variable"] == "visibility" else "1",
                    source_sha256=reference()["source_objects"]["2023"]["sha256"],
                    source_row=1,
                    report_type="FM15",
                    measurement_code="" if row["variable"] == "temperature" else "N",
                    quality_code="1",
                    source_code="343",
                    source_station_id="725650-03017",
                    remarks="",
                    remarks_attributes={},
                )
            ]
        payload = "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
        )
        data = manifest()
        data.update(
            rows=len(rows),
            payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            payload_bytes=len(payload.encode()),
        )
        data["weather_id"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        (path / "manifest.json").write_text(json.dumps(data))
        (path / "observations.jsonl").write_text(payload)
        # Explicit independent trust boundary for this synthetic source fixture.
        from airline_warehouse.weather_trust import TRUSTED

        trust = patch.dict(TRUSTED, data, clear=True)
        trust.start()
        self.addCleanup(trust.stop)
        return data

    def test_real_artifact_read_exact_replay_and_changed_raw_refusal(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LIMITS):
            path = Path(tmp)
            data = self.write_artifact(path)
            self.assertEqual(read_weather(path)[0], data)
            connection = ReplayConnection()
            first = load_weather(connection, path)
            self.assertEqual(load_weather(connection, path), first)
            self.assertEqual(sum(s.startswith("INSERT INTO") for s in connection.statements), 1)
            connection.rows[0] = connection.rows[0].replace('"value":1', '"value":2')
            with self.assertRaisesRegex(ValueError, "no overwrite"):
                load_weather(connection, path)
            with (path / "observations.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "corrupt"):
                read_weather(path)

    def test_measured_limits_required_and_enforced(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "MAX_BYTES"):
                weather_limits(manifest())
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LIMITS):
            self.write_artifact(Path(tmp))
            with patch.dict(os.environ, {"AIRLINE_WEATHER_MAX_FLIGHTS": "930446"}):
                with self.assertRaisesRegex(ValueError, "census envelope"):
                    read_weather(tmp)
            with patch.dict(os.environ, {"AIRLINE_WEATHER_MAX_BYTES": "1"}):
                with self.assertRaisesRegex(ValueError, "input bound"):
                    read_weather(tmp)
            with patch.dict(os.environ, {"AIRLINE_WEATHER_MAX_OBSERVATIONS": "2"}):
                with self.assertRaisesRegex(ValueError, "input bound"):
                    read_weather(tmp)

    def test_pinned_dst_gaps_folds_and_full_period_endpoints(self):
        data = manifest()
        self.assertEqual(
            classified_anchor("2023-11-05", "0119", data), (None, "ambiguous_local_time")
        )
        self.assertEqual(
            classified_anchor("2024-03-10", "0230", data), (None, "nonexistent_local_time")
        )
        self.assertEqual(
            classified_anchor("2023-01-01", "0001", data)[0],
            dt.datetime(2023, 1, 1, 7, 1, tzinfo=dt.UTC),
        )
        self.assertEqual(
            classified_anchor("2025-12-31", "2359", data)[0],
            dt.datetime(2026, 1, 1, 6, 59, tzinfo=dt.UTC),
        )
        for day, clock in (("2026-01-01", "0100"), ("2022-12-31", "1200"), ("2023-01-01", "1260")):
            with self.assertRaises(ValueError):
                classified_anchor(day, clock, data)
        for clock in ("0000", "2400"):
            self.assertEqual(
                classified_anchor("2023-01-01", clock, data), (None, "unresolved_midnight")
            )

    def test_independent_age_boundaries_variable_times_and_rejected_fallback(self):
        anchor = dt.datetime(2023, 1, 1, 15, tzinfo=dt.UTC)
        rows = [
            record("temperature", "2023-01-01T14:00:00+00:00", -1),
            record("temperature", "2023-01-01T15:00:00+00:00", None, "rejected_qc"),
            record("wind", "2023-01-01T15:00:00+00:00", 5),
            record("visibility", "2023-01-01T13:59:59+00:00", 1000),
            record("visibility", "2023-01-01T15:00:01+00:00", 2000),
        ]
        index = observation_index(rows)
        self.assertEqual(oracle_match(index, "temperature", anchor)[1:], (3600, -1, "matched"))
        self.assertEqual(oracle_match(index, "wind", anchor)[1:], (0, 5, "matched"))
        self.assertEqual(oracle_match(index, "visibility", anchor)[1:], (3601, None, "stale"))
        self.assertEqual(
            oracle_match(index, "temperature", anchor - dt.timedelta(hours=2))[-1],
            "no_prior_accepted",
        )
        self.assertEqual(
            oracle_match(index, "wind", None, "ambiguous_local_time"),
            (None, None, None, "ambiguous_local_time"),
        )
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            observation_index(rows + rows[:1])

    def test_explicit_sql_version_dispatch_preserves_january_reconstruction(self):
        schema = "RELEASE_" + "A" * 24
        january = render_weather_sql("den_weather", schema)
        expanded = render_weather_sql("den_weather", schema, manifest())
        gate = render_weather_sql("weather_integrity", schema, manifest())
        self.assertIn("flight_date>='2025-01-01' and flight_date<'2025-02-01'", january)
        self.assertNotIn("anchor_status", january)
        self.assertIn("flight_date>='2023-01-01'", expanded)
        self.assertIn("flight_date<'2026-01-01'", expanded)
        self.assertIn("'1129202','1129203'", expanded)
        self.assertIn("'invalid_mapping'", expanded)
        self.assertIn("'ambiguous_local_time'", expanded)
        self.assertIn("count(*)<0.95", gate)
        self.assertNotIn("2025-02-01", expanded)
        self.assertEqual(weather_variables(manifest())["weather_scope_end"], "2026-01-01")
        with self.assertRaises(ValueError):
            render_weather_sql("den_weather", schema, {**manifest(), "scope_start": "2024-01-01"})

    def test_whole_scope_required_before_publication_or_connection(self):
        from airline_warehouse.publication import publish

        data = manifest()
        with self.assertRaisesRegex(ValueError, "all selected flight months"):
            validate_weather_inputs(data, {"2025-01": "a" * 64})
        validate_weather_inputs(
            data, {f"{y}-{m:02d}": "a" * 64 for y in range(2023, 2026) for m in range(1, 13)}
        )
        with self.assertRaisesRegex(ValueError, "all selected flight months"):
            publish(
                None,
                {"target": "january"},
                dict(
                    sealed=True,
                    schema="WORK_" + "A" * 24,
                    inputs={"2025-01": "a" * 64},
                    weather=data,
                ),
                "a" * 32,
            )

    def test_rehashed_normalized_values_cannot_override_preserved_source_fields(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LIMITS):
            path = Path(tmp)
            data = self.write_artifact(path)
            payload = (path / "observations.jsonl").read_text().replace('"value":1', '"value":2')
            (path / "observations.jsonl").write_text(payload)
            data["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
            data.pop("weather_id")
            data["weather_id"] = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()
            (path / "manifest.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "reviewed source-derived"):
                read_weather(path)

    def test_coordinated_raw_value_and_manifest_rehash_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LIMITS):
            path = Path(tmp)
            data = self.write_artifact(path)
            payload = (path / "observations.jsonl").read_text()
            payload = payload.replace('"value":1', '"value":2').replace('"raw":"1"', '"raw":"2"')
            (path / "observations.jsonl").write_text(payload)
            data["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
            data.pop("weather_id")
            data["weather_id"] = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()
            (path / "manifest.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "reviewed source-derived"):
                read_weather(path)

    def test_frozen_oracle_rejects_guessed_fold_and_invalid_mapping(self):
        class FrozenConnection(ReplayConnection):
            def __init__(self, records, anchor):
                super().__init__()
                self.records, self.anchor = records, anchor
                self.anchor_read = False

            def execute(self, sql, params=None):
                self.statements.append(sql)

            def fetchall(self):
                if "SELECT preserved_record FROM" in self.statements[-1]:
                    return [(r,) for r in self.records]
                return [self.anchor]

            def fetchone(self):
                # Scripted relational reconstruction success; this test specifically
                # exercises the *independent* Python boundary after that SQL gate.
                return None

            def fetchmany(self, size):
                if self.anchor_read:
                    return []
                self.anchor_read = True
                return [self.anchor]

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LIMITS):
            path = Path(tmp)
            data = self.write_artifact(path)
            # Database return order is unspecified; digest canonical observation order.
            records = (path / "observations.jsonl").read_text().splitlines()[::-1]
            anchor = (
                "2023-11-05",
                "0119",
                dt.datetime(2023, 11, 5, 7, 19),
                "ambiguous_local_time",
                "1129202",
                0,
                0,
            ) + (None, None, None, "ambiguous_local_time") * 3
            with self.assertRaisesRegex(ValueError, "pinned America/Denver"):
                validate_frozen_weather(
                    FrozenConnection(records, anchor), "RELEASE_" + "A" * 24, data
                )
            anchor = anchor[:2] + (None, "ambiguous_local_time", "invalid_sequence") + anchor[5:]
            with self.assertRaisesRegex(ValueError, "classification/mapping"):
                validate_frozen_weather(
                    FrozenConnection(records, anchor), "RELEASE_" + "A" * 24, data
                )

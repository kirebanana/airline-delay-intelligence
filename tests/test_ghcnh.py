"""Independent tiny PSV fixtures: never download or depend on acquired NOAA files."""

import datetime as dt
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from airline_warehouse import ghcnh
from airline_warehouse.weather_contract import (
    CONTRACT,
    classify_scheduled_anchor,
    contract_scope,
    mapping_sha256,
    reference,
    verify_mapping,
)

HEADER = ["STATION", "DATE", "LATITUDE", "LONGITUDE", "REM"]
for FIELD in ("temperature", "wind_speed", "visibility"):
    HEADER += [FIELD] + [
        FIELD + "_" + a
        for a in (
            "Measurement_Code",
            "Quality_Code",
            "Report_Type",
            "Source_Code",
            "Source_Station_ID",
        )
    ]


def observation(stamp="2025-01-01T07:53:00", source="223", **updates):
    row = dict.fromkeys(HEADER, "")
    row.update(
        STATION="USW00003017",
        DATE=stamp,
        LATITUDE="39.8467",
        LONGITUDE="-104.6561",
        REM="MET079METAR KDEN 010753Z 16009KT 10SM CLR 08/M07 A3008",
    )
    for field, value, code in (
        ("temperature", "7.8", ""),
        ("wind_speed", "4.6", "N"),
        ("visibility", "16.093", "P" if source == "223" else "N"),
    ):
        row[field] = value
        row[field + "_Measurement_Code"] = code
        row[field + "_Quality_Code"] = "1" if source == "223" else "5"
        row[field + "_Report_Type"] = "FM15"
        row[field + "_Source_Code"] = source
        row[field + "_Source_Station_ID"] = "ICAO-KDEN" if source == "223" else "725650-03017"
    row.update(updates)
    return row


def psv(*rows):
    return (
        "|".join(HEADER) + "\n" + "".join("|".join(row[k] for k in HEADER) + "\n" for row in rows)
    )


def parse(*rows):
    return list(ghcnh.parse_observations(io.StringIO(psv(*rows)), "a" * 64))


def manifest():
    ref = reference()
    return {**ref, "mapping_version": ref["version"], "mapping_sha256": mapping_sha256()}


class DecoderTests(unittest.TestCase):
    def test_units_are_decimal_not_isd_scaled(self):
        actual = {r["variable"]: r["value"] for r in parse(observation())}
        self.assertEqual(actual, {"temperature": 7.8, "wind": 4.6, "visibility": 16093.0})

    def test_qc_is_source_specific(self):
        for source, qc, expected in (
            ("223", "5", "rejected_qc"),
            ("343", "5", "accepted"),
            ("343", "A", "accepted"),
            ("343", "1a", "rejected_qc"),
            ("223", "0", "rejected_qc"),
            ("343", "6", "rejected_qc"),
        ):
            with self.subTest(source=source, qc=qc):
                row = observation(source=source, temperature_Quality_Code=qc)
                self.assertEqual(ghcnh.decode("temperature", row)[1], expected)

    def test_variable_report_types_and_sources_are_independent(self):
        rows = {
            r["variable"]: r
            for r in parse(
                observation(temperature_Report_Type="FM12", wind_speed_Source_Code="999")
            )
        }
        self.assertEqual(rows["temperature"]["status"], "rejected_report_type")
        self.assertEqual(rows["wind"]["status"], "rejected_source")
        self.assertEqual(rows["visibility"]["status"], "accepted")
        self.assertEqual(rows["visibility"]["provenance"][0]["source_station_id"], "ICAO-KDEN")

    def test_visibility_p_is_prevailing_not_censoring(self):
        self.assertEqual(ghcnh.decode("visibility", observation()), (16093.0, "accepted"))
        for qualifier in ("P6SM", "M1/4SM"):
            row = observation(REM=f"METAR KDEN 010753Z 16009KT {qualifier} CLR")
            self.assertEqual(ghcnh.decode("visibility", row), (None, "qualified_visibility"))
        row = observation(source="343", visibility_Measurement_Code="V")
        self.assertEqual(ghcnh.decode("visibility", row)[1], "rejected_measurement")

    def test_wind_normal_calm_and_variable_direction(self):
        for code, value, status in (
            ("C", "0", "accepted"),
            ("V", "4.6", "accepted"),
            ("C", "4.6", "rejected_measurement"),
            ("R", "4.6", "rejected_measurement"),
        ):
            self.assertEqual(
                ghcnh.decode(
                    "wind", observation(wind_speed_Measurement_Code=code, wind_speed=value)
                )[1],
                status,
            )

    def test_missing_malformed_and_unsafe_values(self):
        for raw, expected in (
            ("", "missing"),
            ("-9999", "missing"),
            ("NaN", "malformed"),
            ("Infinity", "malformed"),
            ("500", "malformed"),
        ):
            self.assertEqual(ghcnh.decode("temperature", observation(temperature=raw))[1], expected)

    def test_source_mapping_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "source station"):
            parse(observation(temperature_Source_Station_ID="ICAO-KXXX"))


class ParserTests(unittest.TestCase):
    def test_duplicates_keep_rejections_and_resolve_independently(self):
        rows = parse(observation(temperature_Quality_Code="3"), observation())
        self.assertEqual(len(rows), 3)
        temperature = next(r for r in rows if r["variable"] == "temperature")
        self.assertEqual(temperature["status"], "accepted")
        self.assertEqual(temperature["duplicate_count"], 2)
        self.assertEqual([p["source_row"] for p in temperature["provenance"]], [1, 2])

    def test_conflicting_accepted_ties_fail(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            parse(observation(), observation(temperature="8.0"))

    def test_exact_utc_envelope(self):
        rows = parse(
            *(
                observation(stamp=s)
                for s in (
                    "2023-01-01T05:59:00",
                    "2023-01-01T06:00:00",
                    "2026-01-01T06:59:00",
                    "2026-01-01T07:00:00",
                )
            )
        )
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["observed_at"], "2023-01-01T06:00:00+00:00")
        self.assertEqual(rows[-1]["observed_at"], "2026-01-01T06:59:00+00:00")

    def test_bad_headers_width_station_order_and_truncation(self):
        texts = [
            psv(observation()).replace("|DATE|", "|STATION|"),
            psv(observation()) + "bad|row\n",
            psv(observation(STATION="USW00000000")),
            psv(observation(), observation(stamp="2025-01-01T07:52:00")),
            psv(observation())[:-1],
        ]
        for text in texts:
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                list(ghcnh.parse_observations(io.StringIO(text), "b" * 64))

    def test_bounded_reads_and_duplicate_groups(self):
        with self.assertRaises(ValueError):
            list(ghcnh.parse_observations(io.StringIO("x" * (ghcnh.MAX_LINE + 1)), "a" * 64))
        with patch.object(ghcnh, "MAX_REPORTS_PER_TIME", 1), self.assertRaises(ValueError):
            parse(observation(), observation())


class ContractTests(unittest.TestCase):
    def test_v2_scope_and_dependency_verification(self):
        self.assertEqual(contract_scope(manifest())["scope_start"], "2023-01-01")
        verify_mapping(manifest())
        for key, value in (
            ("contract", "unknown"),
            ("scope_start", "2024-01-01"),
            ("mapping_sha256", "a" * 64),
            ("timezone_sha256", "b" * 64),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_mapping({**manifest(), key: value})

    def test_dst_no_fold_guess(self):
        for date, clock, expected in (
            ("2023-11-05", "0119", "ambiguous_local_time"),
            ("2024-03-10", "0230", "nonexistent_local_time"),
            ("2025-01-01", "0000", "unresolved_midnight"),
            ("2025-01-01", "2400", "unresolved_midnight"),
        ):
            self.assertEqual(classify_scheduled_anchor(date, clock, manifest()), (None, expected))
        actual, status = classify_scheduled_anchor("2025-07-01", "0004", manifest())
        self.assertEqual(actual, dt.datetime(2025, 7, 1, 6, 4, tzinfo=dt.UTC))
        self.assertEqual(status, "resolved")

    def test_invalid_times_are_not_waivers(self):
        for date, clock in (
            ("2022-12-31", "0500"),
            ("2025-01-01", "1260"),
            ("2025-01-01", "2500"),
            ("2025-01-01", "5:00"),
        ):
            with self.assertRaises(ValueError):
                classify_scheduled_anchor(date, clock, manifest())

    def test_legacy_scope_without_new_local_fields(self):
        old = {
            "contract": "den-isd-aviation-qc15-independent-60m-v1",
            "station": "72565003017",
            "origin_id": 11292,
            "start": "2025-01-01T06:00:00+00:00",
            "end": "2025-02-01T07:00:00+00:00",
        }
        self.assertEqual(contract_scope(old)["scope_end_exclusive"], "2025-02-01")
        self.assertEqual(classify_scheduled_anchor("2025-01-01", "0500", old)[1], "resolved")


class ArtifactTests(unittest.TestCase):
    def test_create_read_replay_tamper_and_boundary_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources, sizes = [], {}
            for year in range(2023, 2027):
                path = root / f"GHCNh_USW00003017_{year}.psv"
                text = psv(observation(stamp=f"{year}-01-01T06:53:00"))
                if year == 2026:
                    text = (
                        psv(
                            observation(stamp="2026-01-01T06:53:00"),
                            observation(stamp="2026-01-01T07:53:00"),
                        )
                        + "partial"
                    )
                path.write_text(text)
                sources.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
                sizes[year] = path.stat().st_size
            fixture_ref = {
                **reference(),
                "source_objects": {
                    str(year): {"sha256": sha, "etag": "offline-fixture"}
                    for year, (_, sha) in zip(range(2023, 2027), sources, strict=True)
                },
            }
            with (
                patch.object(ghcnh, "SOURCE_SIZES", sizes),
                patch.object(ghcnh, "reference", return_value=fixture_ref),
            ):
                first = ghcnh.prepare_ghcnh(sources, root / "first")
                second = ghcnh.prepare_ghcnh(sources, root / "second")
                self.assertEqual(first, second)
                self.assertEqual(first["contract"], CONTRACT)
                self.assertEqual(first["rows"], 12)
                self.assertEqual(first["sources"][-1]["discarded_partial_bytes"], 7)
                self.assertEqual(ghcnh.read_ghcnh(root / "first")[0], first)
                with self.assertRaises(ValueError):
                    ghcnh.prepare_ghcnh(sources, root / "first")
                broken = [(sources[0][0], "a" * 64), *sources[1:]]
                with self.assertRaisesRegex(ValueError, "checksum"):
                    ghcnh.prepare_ghcnh(broken, root / "broken")
                self.assertFalse((root / "broken").exists())
                payload = root / "first/observations.jsonl"
                payload.write_text(payload.read_text().replace('"value":7.8', '"value":8.8'))
                with self.assertRaisesRegex(ValueError, "payload"):
                    ghcnh.read_ghcnh(root / "first")
                doc = json.loads((root / "second/manifest.json").read_text())
                doc["scope_start"] = "2024-01-01"
                (root / "second/manifest.json").write_text(json.dumps(doc))
                with self.assertRaises(ValueError):
                    ghcnh.read_ghcnh(root / "second")


if __name__ == "__main__":
    unittest.main()

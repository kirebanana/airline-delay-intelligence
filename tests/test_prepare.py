import csv
import gzip
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from airline_warehouse.prepare import BTS_COLUMNS, PreparationError, prepare


def archive(path, rows, header=None, member=None):
    """Synthetic, hand-authored test rows; never represented as official data."""
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow([*(header or BTS_COLUMNS), ""])
    for changes in rows:
        row = {name: "" for name in BTS_COLUMNS}
        row.update(
            Year="2025",
            Quarter="1",
            Month="1",
            DayofMonth="1",
            DayOfWeek="3",
            FlightDate="2025-01-01",
            Origin="DEN",
            OriginAirportID="11292",
            OriginAirportSeqID="1129202",
            Dest="SFO",
            Cancelled="0.00",
            Diverted="0.00",
            Duplicate="N",
            Flights="1.00",
            CRSDepTime="0029",
        )
        row.update(changes)
        writer.writerow([*(row[n] for n in BTS_COLUMNS), ""])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            member
            or (
                "On_Time_Marketing_Carrier_On_Time_Performance_(Beginning_January_2018)_2025_1.csv"
            ),
            text.getvalue(),
        )
        z.writestr("readme.html", "Marketing Carrier On-Time Performance (Beginning January 2018)")


class PreparationTests(unittest.TestCase):
    def test_row_output_and_time_budgets_fail_without_a_manifest(self):
        for target in ("MAX_ROWS", "MAX_OUTPUT_BYTES", "MAX_EXPANDED_BYTES"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive(root / "source.zip", [{}, {}])
                with patch("airline_warehouse.prepare." + target, 1):
                    with self.assertRaises(PreparationError):
                        prepare(root / "source.zip", root / "out", "2025-01", synthetic=True)
                self.assertFalse((root / "out" / "manifest.json").exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive(root / "source.zip", [{}])
            with patch("airline_warehouse.prepare.time.monotonic", side_effect=[0, 1000]):
                with self.assertRaises(PreparationError):
                    prepare(root / "source.zip", root / "out", "2025-01", synthetic=True)
            self.assertFalse((root / "out" / "manifest.json").exists())

    def test_prepare_preserves_source_values_and_has_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            archive(
                source,
                [
                    {"ArrDelay": "-10.00", "DepDel15": "0.00", "OriginCityName": 'Dénver, "CO"'},
                    {"ArrDelay": "14.00", "DepDel15": "0.00"},
                    {"ArrDelay": "15.00", "DepDel15": "1.00", "Duplicate": "Y"},
                    {"Cancelled": "1.00", "DepTime": "1200", "CancellationCode": "B"},
                    {"Diverted": "1.00", "ArrDelay": "", "Flights": "1.00"},
                    {"Cancelled": "", "ArrDel15": ""},
                ],
            )
            first = prepare(source, root / "one", "2025-01", synthetic=True)
            second = prepare(source, root / "two", "2025-01", synthetic=True)
            self.assertEqual(first, second)
            self.assertEqual(first["rows"], 6)
            self.assertEqual(first["profile"]["cancelled"], {"0.00": 4, "1.00": 1, "": 1})
            a = root / "one" / "prepared.csv.gz"
            self.assertEqual(a.read_bytes(), (root / "two" / a.name).read_bytes())
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), first["prepared_sha256"])
            with gzip.open(a, "rt", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["ArrDelay"], "-10.00")
            self.assertEqual(rows[0]["OriginCityName"], 'Dénver, "CO"')
            self.assertEqual(rows[2]["Duplicate"], "Y")
            self.assertEqual(rows[3]["DepTime"], "1200")
            self.assertEqual(rows[4]["ArrDelay"], "")
            self.assertEqual([r["SOURCE_ROW_NUMBER"] for r in rows], ["1", "2", "3", "4", "5", "6"])
            self.assertEqual(json.loads((root / "one" / "manifest.json").read_text()), first)

    def test_only_documented_header_quirks_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            header = ["Operating_Airline " if s == "Operating_Airline" else s for s in BTS_COLUMNS]
            header[0] = " Year "  # not a documented source quirk
            archive(source, [{}], header=header)
            with self.assertRaises(PreparationError):
                prepare(source, root / "output", "2025-01", synthetic=True)
            self.assertFalse((root / "output").exists())

    def test_rejects_bad_source_contracts_without_completion(self):
        for label, changes, kwargs in [
            ("month", {"FlightDate": "2024-12-31"}, {}),
            ("weekday", {"DayOfWeek": "1"}, {}),
            ("calendar", {"FlightDate": "2025-01-99"}, {}),
            ("nul", {"Tail_Number": "BAD\x00VALUE"}, {}),
            ("mapping", {"OriginAirportID": "99999"}, {}),
            ("schema", {}, {"header": ["Wrong"] + BTS_COLUMNS[1:]}),
            ("member", {}, {"member": "../source.csv"}),
        ]:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source.zip"
                archive(source, [changes], **kwargs)
                with self.assertRaises(PreparationError):
                    prepare(source, root / "output", "2025-01", synthetic=True)
                self.assertFalse((root / "output" / "manifest.json").exists())

    def test_wrong_hash_and_existing_output_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            archive(source, [{}])
            with self.assertRaises(PreparationError):
                prepare(source, root / "out", "2025-01", expected_sha256="0" * 64)
            result = prepare(source, root / "out", "2025-01", synthetic=True)
            with self.assertRaises(PreparationError):
                prepare(source, root / "out", "2025-01", synthetic=True)
            self.assertEqual(json.loads((root / "out" / "manifest.json").read_text()), result)

    def test_corrupt_zip_and_invalid_month_leave_no_completed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            source.write_bytes(b"not a ZIP")
            for month in ["../2025-01", "2025-13", "2025-01"]:
                with self.subTest(month=month), self.assertRaises((ValueError, zipfile.BadZipFile)):
                    prepare(source, root / "out", month)
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()

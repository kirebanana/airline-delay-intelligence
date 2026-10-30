import datetime as dt
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from airline_warehouse.weather import (
    decode,
    parse_observations,
    prepare_weather,
    read_weather,
    scheduled_anchor,
)


class WeatherPreparationTests(unittest.TestCase):
    def test_prepared_weather_identity_replay_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            source.write_text(
                "STATION,DATE,REPORT_TYPE,CALL_SIGN,TMP,WND,VIS\n"
                "72565003017,2025-01-01T07:00:00,FM-15,KDEN ,"
                '"+0010,1","000,1,N,0050,1","001600,1,N,1"\n'
            )
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            a = prepare_weather([(source, checksum)], root / "a")
            b = prepare_weather([(source, checksum)], root / "b")
            self.assertEqual(a, b)
            self.assertEqual(read_weather(root / "a")[0], a)
            with self.assertRaises(ValueError):
                prepare_weather([(source, checksum)], root / "a")
            data = json.loads((root / "a/manifest.json").read_text())
            data["rows"] = 1
            (root / "a/manifest.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "corrupt"):
                read_weather(root / "a")

    def test_field_qc_units_sentinels_and_full_local_calendar_anchor(self):
        self.assertEqual(decode("temperature", "-0123,1"), (-12.3, "accepted"))
        self.assertEqual(decode("wind", "000,1,N,0050,5"), (5.0, "accepted"))
        self.assertEqual(decode("visibility", "001600,1,N,1"), (1600.0, "accepted"))
        self.assertEqual(decode("temperature", "+9999,1"), (None, "missing"))
        self.assertEqual(decode("wind", "000,1,N,9999,1"), (None, "missing"))
        self.assertEqual(decode("visibility", "999999,1,N,1"), (None, "missing"))
        self.assertEqual(decode("temperature", "+0100,6"), (None, "rejected_qc"))
        self.assertEqual(decode("temperature", "nonsense"), (None, "malformed"))
        self.assertEqual(
            scheduled_anchor("2025-01-31", "2359"), dt.datetime(2025, 2, 1, 6, 59, tzinfo=dt.UTC)
        )
        for clock in ("2400", "0000", "1260", "", "-1"):
            with self.assertRaises(ValueError):
                scheduled_anchor("2025-01-01", clock)

    def test_duplicate_headers_and_conflicting_accepted_ties_fail_closed(self):
        header = "STATION,DATE,REPORT_TYPE,CALL_SIGN,TMP,WND,VIS,STATION\n"
        row = (
            "72565003017,2025-01-01T07:00:00,FM-15,KDEN,"
            '"+0010,1","000,1,N,0050,1","001600,1,N,1",72565003017\n'
        )
        parsed = parse_observations(io.StringIO(header + row + row), "a" * 64)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["duplicate_count"], 2)
        with self.assertRaisesRegex(ValueError, "Conflicting accepted"):
            parse_observations(io.StringIO(header + row + row.replace("+0010", "+0020")), "a" * 64)
        with self.assertRaisesRegex(ValueError, "Repeated"):
            parse_observations(
                io.StringIO(header + row.replace(",72565003017\n", ",other\n")), "a" * 64
            )

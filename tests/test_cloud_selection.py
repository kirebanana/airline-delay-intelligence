import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from airline_warehouse.cloud_selection import read_selection, selection_digest


class CloudSelectionTests(unittest.TestCase):
    def read(self, value):
        body = json.dumps(value).encode()
        digest = hashlib.sha256(body).hexdigest()
        ref = {"key": f"manifests/selections/{digest}.json", "sha256": digest}
        s3 = Mock()
        s3.get_object.return_value = {"Body": io.BytesIO(body)}
        return read_selection(s3, ref), s3

    def test_selection_supports_36_unique_months_without_large_task_overrides(self):
        artifacts = [
            {
                "key": f"manifests/prepared/bts/{year}-{month:02d}/"
                + "a" * 64
                + "/"
                + "b" * 64
                + ".json",
                "sha256": "c" * 64,
            }
            for year in range(2023, 2026)
            for month in range(1, 13)
        ]
        value = {"artifacts": artifacts, "weather": None}
        actual, _ = self.read(value)
        self.assertEqual(actual, value)
        self.assertEqual(selection_digest({"b": 2, "a": 1}), selection_digest({"a": 1, "b": 2}))

    def test_selection_rejects_empty_duplicate_month_outside_scope_and_extra_fields(self):
        artifact = {
            "key": "manifests/prepared/bts/2025-01/" + "a" * 64 + "/" + "b" * 64 + ".json",
            "sha256": "c" * 64,
        }
        for value in (
            {"artifacts": [], "weather": None},
            {"artifacts": [artifact, artifact], "weather": None},
            {"artifacts": [{**artifact, "key": "state/secret"}], "weather": None},
            {"artifacts": [artifact], "weather": None, "command": "no"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read(value)

    def test_weather_is_hash_checked_and_restored_for_existing_business_adapter(self):
        from airline_warehouse.cloud_selection import restore_weather
        from airline_warehouse.weather import prepare_weather, read_weather

        source = (
            b"STATION,DATE,REPORT_TYPE,CALL_SIGN,TMP,WND,VIS\n"
            b'72565003017,2025-01-01T07:00:00,FM-15,KDEN,"+0010,1",'
            b'"090,1,N,0010,1","010000,1,9,9"\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "source.csv"
            path.write_bytes(source)
            manifest = prepare_weather(
                [(path, hashlib.sha256(source).hexdigest())], root / "prepared"
            )
            mid = manifest["weather_id"]
            mbody = (root / "prepared/manifest.json").read_bytes()
            pbody = (root / "prepared/observations.jsonl").read_bytes()
            ref = {
                "manifest": {
                    "key": f"manifests/prepared/weather/isd/72565003017/{mid}.json",
                    "sha256": hashlib.sha256(mbody).hexdigest(),
                },
                "observations": {
                    "key": f"prepared/weather/isd/72565003017/{mid}/observations.jsonl",
                    "sha256": hashlib.sha256(pbody).hexdigest(),
                },
            }
            s3 = Mock()
            s3.get_object.side_effect = [{"Body": io.BytesIO(mbody)}, {"Body": io.BytesIO(pbody)}]
            restored = restore_weather(s3, ref, root / "restored")
            self.assertEqual(read_weather(restored)[0], manifest)
            s3.get_object.side_effect = [
                {"Body": io.BytesIO(mbody)},
                {"Body": io.BytesIO(b"corrupt")},
            ]
            with self.assertRaises(ValueError):
                restore_weather(s3, ref, root / "corrupt")

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_prepare import archive

from airline_warehouse.acquire import acquire_month


class OfficialAcquisitionTests(unittest.TestCase):
    def test_validator_bound_ranges_reconstruct_exact_bytes_without_mixing_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive(root / "fixture.zip", [{}])
            body = (root / "fixture.zip").read_bytes()

            class Response(io.BytesIO):
                url = "https://www.transtats.bts.gov/PREZIP/official.zip"
                status = 206

            def wire(request, **kwargs):
                value = request.get_header("Range")
                start, end = map(int, value.removeprefix("bytes=").split("-"))
                response = Response(body[start : end + 1])
                response.headers = {
                    "Content-Length": str(end - start + 1),
                    "Content-Range": f"bytes {start}-{end}/{len(body)}",
                    "ETag": '"same-snapshot"',
                }
                return response

            with patch("airline_warehouse.acquire.urllib.request.urlopen", side_effect=wire):
                result = acquire_month("2025-01", root / "output", ranged=True)
            self.assertEqual(result["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual((root / "output/source.zip").read_bytes(), body)

    def test_explicit_official_month_preserves_original_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive(root / "fixture.zip", [{}])
            body = (root / "fixture.zip").read_bytes()

            class Response(io.BytesIO):
                headers = {"Content-Length": str(len(body)), "ETag": "fixture-validator"}
                url = "https://www.transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2025_1.zip"

            with patch(
                "airline_warehouse.acquire.urllib.request.urlopen", return_value=Response(body)
            ) as wire:
                result = acquire_month("2025-01", root / "output")
            self.assertEqual(result["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual((root / "output/source.zip").read_bytes(), body)
            self.assertEqual(wire.call_count, 1)
            with self.assertRaises(ValueError):
                acquire_month("2025-01", root / "output")

    def test_invalid_month_refuses_network(self):
        with patch("airline_warehouse.acquire.urllib.request.urlopen") as wire:
            with self.assertRaises(ValueError):
                acquire_month("2025-13", Path("/not-created"))
            wire.assert_not_called()

    def test_changed_range_validator_never_completes_an_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive(root / "fixture.zip", [{}])
            body = (root / "fixture.zip").read_bytes()
            calls = []

            class Response(io.BytesIO):
                url = "https://www.transtats.bts.gov/PREZIP/official.zip"
                status = 206

            def wire(request, **kwargs):
                calls.append(request)
                start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
                response = Response(body[start : end + 1])
                response.headers = {
                    "Content-Length": str(end - start + 1),
                    "Content-Range": f"bytes {start}-{end}/{len(body)}",
                    "ETag": '"first"' if len(calls) == 1 else '"changed"',
                }
                return response

            with patch("airline_warehouse.acquire.urllib.request.urlopen", side_effect=wire):
                with self.assertRaisesRegex(ValueError, "validator changed"):
                    acquire_month("2025-01", root / "output", ranged=True)
            self.assertEqual(calls[1].get_header("If-match"), '"first"')
            self.assertFalse((root / "output/retrieval.json").exists())
            self.assertFalse((root / "output/source.zip").exists())

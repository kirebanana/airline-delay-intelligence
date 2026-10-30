"""Explicit bounded official BTS monthly acquisition; no discovery or silent fallback."""

import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from airline_warehouse.prepare import MAX_EXPANDED_BYTES, MAX_ZIP_BYTES


def _open_source(request, timeout):
    response = urllib.request.urlopen(request, timeout=timeout)
    final = urllib.parse.urlparse(response.url)
    if final.scheme != "https" or final.hostname not in (
        "www.transtats.bts.gov",
        "transtats.bts.gov",
    ):
        response.close()
        raise ValueError("Unexpected official-source redirect")
    return response


def _ranged_download(url, output, deadline):
    """Explicit bounded transport alternative, pinned to one strong source ETag."""

    def open_range(start, end, etag=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Ranged acquisition deadline exhausted")
        headers = {
            "User-Agent": "AirlineDelayIntelligence/1.0 bounded academic import",
            "Range": f"bytes={start}-{end}",
        }
        if etag:
            headers["If-Match"] = etag
        return _open_source(
            urllib.request.Request(url, headers=headers), timeout=min(45, remaining)
        )

    with open_range(0, 0) as probe:
        match = re.fullmatch(r"bytes 0-0/([0-9]+)", probe.headers.get("Content-Range", ""))
        etag = probe.headers.get("ETag")
        if probe.status != 206 or not match or not etag or etag.startswith("W/"):
            raise ValueError("Ranged import requires an exact range and strong source validator")
        total = int(match[1])
        if not 0 < total <= MAX_ZIP_BYTES or len(probe.read(2)) != 1:
            raise ValueError("Invalid range probe size")
        validators = {n: probe.headers.get(n) for n in ("ETag", "Last-Modified")}
    (output / "range-probe.json").write_text(
        json.dumps(dict(bytes=total, validators=validators)) + "\n"
    )
    pieces = [
        (i, start, min(start + 4 * 1024**2, total) - 1)
        for i, start in enumerate(range(0, total, 4 * 1024**2))
    ]

    def receive(piece):
        i, start, end = piece
        path = output / f"range-{i:03d}.partial"
        size = 0
        with open_range(start, end, etag) as response, path.open("xb") as stream:
            final = urllib.parse.urlparse(response.url)
            if (
                final.scheme != "https"
                or final.hostname not in ("www.transtats.bts.gov", "transtats.bts.gov")
                or response.status != 206
                or response.headers.get("ETag") != etag
                or response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}"
            ):
                raise ValueError("Source range/validator changed; refuse mixed source versions")
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Ranged acquisition deadline")
                block = response.read(64 * 1024)
                if not block:
                    break
                size += len(block)
                if size > end - start + 1:
                    raise ValueError("Oversized source range")
                stream.write(block)
        if size != end - start + 1:
            raise ValueError("Incomplete source range")
        return path

    with ThreadPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(receive, pieces))
    with (output / "source.partial").open("xb") as assembled:
        for path in paths:
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Range assembly deadline")
                    assembled.write(block)
    return total, validators


def acquire_month(month, output, *, timeout_seconds=300, ranged=False):
    if not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", month) or month < "2018-01":
        raise ValueError("Explicit supported marketing-table month required")
    if not 1 <= timeout_seconds <= 300:
        raise ValueError("Acquisition must fit the five-minute partition allowance")
    output = Path(output)
    if output.exists():
        raise ValueError("Acquisition output exists; never overwrite preserved inputs")
    output.mkdir(parents=True, exist_ok=False)
    year, number = map(int, month.split("-"))
    url = (
        "https://www.transtats.bts.gov/PREZIP/"
        f"On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_{year}_{number}.zip"
    )
    deadline = time.monotonic() + timeout_seconds
    intent = dict(
        month=month,
        url=url,
        retrieved_at=dt.datetime.now(dt.UTC).isoformat(),
        transport="validator-bound-ranges" if ranged else "single-response",
    )
    (output / "intent.json").write_text(json.dumps(intent, indent=2) + "\n")
    path = output / "source.partial"
    digest = hashlib.sha256()
    size = 0
    try:
        if ranged:
            size, validators = _ranged_download(url, output, deadline)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256")
        else:
            size, validators = _single_download(url, path, deadline, digest, timeout_seconds)
        with zipfile.ZipFile(path) as archive:
            if sum(m.file_size for m in archive.infolist()) > MAX_EXPANDED_BYTES:
                raise ValueError("Archive expansion exceeds one-GiB envelope")
            for member in archive.infolist():
                with archive.open(member) as stream:
                    while stream.read(1024 * 1024):
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Acquisition CRC validation deadline exhausted")
        if time.monotonic() >= deadline:
            raise TimeoutError("Acquisition completion deadline exhausted")
        result = {
            **intent,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "validators": validators,
            "status": "ACQUIRED",
            "source": "official-bts-monthly-archive",
        }
        path.rename(output / "source.zip")
        (output / "retrieval.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except BaseException as error:
        (output / "failure.json").write_text(
            json.dumps(
                dict(
                    status="UNACCEPTED",
                    error_type=type(error).__name__,
                    received_bytes=path.stat().st_size if path.exists() else 0,
                )
            )
            + "\n"
        )
        raise


def _single_download(url, path, deadline, digest, timeout_seconds):
    size = 0
    request = urllib.request.Request(
        url, headers={"User-Agent": "AirlineDelayIntelligence/1.0 bounded academic import"}
    )
    with (
        _open_source(request, timeout=min(30, timeout_seconds)) as response,
        path.open("xb") as stream,
    ):
        final = urllib.parse.urlparse(response.url)
        if final.scheme != "https" or final.hostname not in (
            "www.transtats.bts.gov",
            "transtats.bts.gov",
        ):
            raise ValueError("Unexpected official-source redirect")
        declared = response.headers.get("Content-Length")
        if declared is not None and not 0 < int(declared) <= MAX_ZIP_BYTES:
            raise ValueError("Official archive exceeds bounded size")
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Acquisition absolute deadline exhausted")
            block = response.read(64 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_ZIP_BYTES:
                raise ValueError("Official archive exceeds bounded size")
            digest.update(block)
            stream.write(block)
        if declared is not None and size != int(declared):
            raise ValueError("Incomplete official archive body; preserve partial diagnostics")
        validators = {n: response.headers.get(n) for n in ("ETag", "Last-Modified")}
    return size, validators

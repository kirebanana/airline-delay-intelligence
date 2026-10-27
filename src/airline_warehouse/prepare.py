"""Stream the complete, source-shaped BTS marketing CSV into deterministic gzip CSV.

Empty source fields stay empty (raw SQL must not impute nulls or outcomes). Lineage
uses a ZIP hash plus one-based data-row ordinal, not a physical-flight business key.
"""

import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

# Reviewed BTS marketing table: 119 named columns. Only the documented trailing
# blank column and Operating_Airline's trailing header whitespace are normalized.
BTS_COLUMNS = """Year Quarter Month DayofMonth DayOfWeek FlightDate
Marketing_Airline_Network Operated_or_Branded_Code_Share_Partners
DOT_ID_Marketing_Airline IATA_Code_Marketing_Airline Flight_Number_Marketing_Airline
Originally_Scheduled_Code_Share_Airline DOT_ID_Originally_Scheduled_Code_Share_Airline
IATA_Code_Originally_Scheduled_Code_Share_Airline Flight_Num_Originally_Scheduled_Code_Share_Airline
Operating_Airline DOT_ID_Operating_Airline IATA_Code_Operating_Airline Tail_Number
Flight_Number_Operating_Airline OriginAirportID OriginAirportSeqID OriginCityMarketID
Origin OriginCityName OriginState OriginStateFips OriginStateName OriginWac DestAirportID
DestAirportSeqID DestCityMarketID Dest DestCityName DestState DestStateFips DestStateName
DestWac CRSDepTime DepTime DepDelay DepDelayMinutes DepDel15 DepartureDelayGroups
DepTimeBlk TaxiOut WheelsOff WheelsOn TaxiIn CRSArrTime ArrTime ArrDelay ArrDelayMinutes
ArrDel15 ArrivalDelayGroups ArrTimeBlk Cancelled CancellationCode Diverted CRSElapsedTime
ActualElapsedTime AirTime Flights Distance DistanceGroup CarrierDelay WeatherDelay NASDelay
SecurityDelay LateAircraftDelay FirstDepTime TotalAddGTime LongestAddGTime DivAirportLandings
DivReachedDest DivActualElapsedTime DivArrDelay DivDistance Div1Airport Div1AirportID
Div1AirportSeqID Div1WheelsOn Div1TotalGTime Div1LongestGTime Div1WheelsOff Div1TailNum
Div2Airport Div2AirportID Div2AirportSeqID Div2WheelsOn Div2TotalGTime Div2LongestGTime
Div2WheelsOff Div2TailNum Div3Airport Div3AirportID Div3AirportSeqID Div3WheelsOn
Div3TotalGTime Div3LongestGTime Div3WheelsOff Div3TailNum Div4Airport Div4AirportID
Div4AirportSeqID Div4WheelsOn Div4TotalGTime Div4LongestGTime Div4WheelsOff Div4TailNum
Div5Airport Div5AirportID Div5AirportSeqID Div5WheelsOn Div5TotalGTime Div5LongestGTime
Div5WheelsOff Div5TailNum Duplicate""".split()

LINEAGE = ["SOURCE_SHA256", "SOURCE_ROW_NUMBER", "SOURCE_ROW_SHA256"]
CONTRACT = "bts-marketing-csv-v1"
MAX_ZIP_BYTES = 100 * 1024**2
MAX_EXPANDED_BYTES = 1024**3
MAX_OUTPUT_BYTES = 200 * 1024**2
MAX_ROWS = 1_000_000


class PreparationError(ValueError):
    """Input or artifact violates the reviewed contract; no retry/repair implied."""


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def row_fingerprint(values: list[str]) -> str:
    # Length-delimited Unicode text is unambiguous even with commas/newlines/colons;
    # Snowflake can independently reproduce this with LENGTH and SHA2 (UTF-8).
    value = "".join(f"{len(cell)}:{cell}" for cell in values)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def prepare(
    archive: Path,
    output: Path,
    month: str,
    *,
    synthetic: bool = False,
    expected_sha256: str | None = None,
    timeout_seconds: int = 300,
) -> dict:
    """Validate an explicit local official import; atomically complete a new artifact.

    No extraction, network, credentials, warehouse calls or accepted-output overwrite.
    A caller can compare manifests from two separate outputs to verify repeatability.
    """
    archive, output = Path(archive), Path(output)
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
        raise PreparationError("Month must be YYYY-MM")
    if timeout_seconds <= 0 or timeout_seconds > 600:
        raise PreparationError("Preparation timeout must be 1–600 seconds")
    if not archive.is_file() or archive.stat().st_size > MAX_ZIP_BYTES:
        raise PreparationError("Archive missing or exceeds 100 MiB")
    source_sha = sha256_file(archive)
    if expected_sha256 is not None and source_sha != expected_sha256:
        raise PreparationError("Source checksum does not match the selected official snapshot")
    if output.exists():
        raise PreparationError("Output already exists; accepted artifacts are never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=".preparing-", dir=output.parent))
    deadline = time.monotonic() + timeout_seconds
    try:
        manifest = _prepare(archive, workspace, month, synthetic, source_sha, deadline)
        # Completion marker is last. Rename a newly created directory, never merge
        # into an existing accepted directory (the exclusive claim handles a race).
        (workspace / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        output.mkdir()  # exclusive destination claim; no clobber on concurrent import
        for name in ("prepared.csv.gz", "manifest.json"):
            os.replace(workspace / name, output / name)
        return manifest
    finally:
        shutil.rmtree(workspace)


def _prepare(archive, workspace, month, synthetic, source_sha, deadline):
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) != len({m.filename for m in members}):
            raise PreparationError("Duplicate ZIP member names")
        if any(Path(m.filename).name != m.filename or m.flag_bits & 1 for m in members):
            raise PreparationError("Unsafe paths or encrypted ZIP members")
        if sum(m.file_size for m in members) > MAX_EXPANDED_BYTES:
            raise PreparationError("Archive expansion exceeds 1 GiB")
        csv_members = [m for m in members if m.filename.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise PreparationError("Expected exactly one source CSV")
        member = csv_members[0]
        year, number = map(int, month.split("-"))
        expected_name = (
            f"On_Time_Marketing_Carrier_On_Time_Performance_(Beginning_January_2018)_{year}_"
        )
        if not re.fullmatch(re.escape(expected_name) + f"0?{number}" + r"\.csv", member.filename):
            raise PreparationError(
                "CSV member does not identify the selected marketing table/month"
            )
        if "readme.html" not in z.namelist() or z.getinfo("readme.html").file_size > 100_000:
            raise PreparationError("Missing or oversized official schema readme")
        if b"Marketing Carrier" not in z.read("readme.html"):
            raise PreparationError("Wrong source table readme")
        counts = {k: collections.Counter() for k in ("cancelled", "diverted", "duplicate")}
        den_rows, den_cancelled, den_diverted = 0, 0, 0
        payload = hashlib.sha256()
        rows = 0
        prepared = workspace / "prepared.csv.gz"
        with (
            z.open(member) as raw,
            io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream,
        ):
            reader = csv.reader(stream, strict=True)
            header = next(reader)
            normalized = ["Operating_Airline" if s == "Operating_Airline " else s for s in header]
            trailing = bool(normalized and normalized[-1] == "")
            fields = normalized[:-1] if trailing else normalized
            if fields != BTS_COLUMNS or len(set(fields)) != len(fields):
                raise PreparationError(
                    "Unexpected BTS schema, order or duplicate normalized header"
                )
            with (
                prepared.open("wb") as compressed,
                gzip.GzipFile(
                    filename="", mode="wb", compresslevel=6, mtime=0, fileobj=compressed
                ) as gz,
            ):

                def write_record(values):
                    text = io.StringIO(newline="")
                    csv.writer(text, lineterminator="\n").writerow(values)
                    data = text.getvalue().encode("utf-8")
                    payload.update(data)
                    gz.write(data)

                write_record(LINEAGE + BTS_COLUMNS)
                for rows, values in enumerate(reader, start=1):
                    if rows > MAX_ROWS or time.monotonic() > deadline:
                        raise PreparationError("Row/time preparation budget exceeded")
                    if len(values) != len(header) or (trailing and values[-1] != ""):
                        raise PreparationError(
                            f"Source row {rows}: invalid CSV width/trailing field"
                        )
                    values = values[:-1] if trailing else values
                    if any("\x00" in cell for cell in values):
                        raise PreparationError(
                            f"Source row {rows}: NUL is not a supported text value"
                        )
                    row = dict(zip(BTS_COLUMNS, values, strict=True))
                    try:
                        day = dt.date.fromisoformat(row["FlightDate"])
                        valid = (
                            day.strftime("%Y-%m") == month
                            and int(row["Year"]) == day.year
                            and int(row["Month"]) == day.month
                            and int(row["DayofMonth"]) == day.day
                            and int(row["Quarter"]) == (day.month - 1) // 3 + 1
                            and int(row["DayOfWeek"]) == day.isoweekday()
                        )
                    except ValueError:
                        valid = False
                    if not valid:
                        raise PreparationError(
                            f"Source row {rows}: wrong partition or invalid calendar"
                        )
                    for name, source in (
                        ("cancelled", "Cancelled"),
                        ("diverted", "Diverted"),
                        ("duplicate", "Duplicate"),
                    ):
                        counts[name][row[source]] += 1
                    if (row["Origin"] == "DEN") != (row["OriginAirportID"] == "11292"):
                        raise PreparationError(
                            f"Source row {rows}: DEN code/stable ID disagreement"
                        )
                    if row["OriginAirportID"] == "11292":
                        den_rows += 1
                        den_cancelled += row["Cancelled"] == "1.00"
                        den_diverted += row["Diverted"] == "1.00"
                    write_record([source_sha, str(rows), row_fingerprint(values), *values])
                    if compressed.tell() > MAX_OUTPUT_BYTES:
                        raise PreparationError("Compressed output exceeds 200 MiB")
        if rows == 0:
            raise PreparationError("Empty source month")
        if prepared.stat().st_size > MAX_OUTPUT_BYTES or time.monotonic() > deadline:
            raise PreparationError("Final output/time preparation budget exceeded")
        prepared_sha = sha256_file(prepared)
        loaded_id = hashlib.sha256(
            f"{source_sha}:{CONTRACT}:{prepared_sha}".encode("ascii")
        ).hexdigest()
        return {
            "manifest_version": 1,
            "preparation_contract": CONTRACT,
            "source_kind": "synthetic-fixture" if synthetic else "official-local-import",
            "dataset": "BTS marketing on-time performance beginning January 2018",
            "source_url": None
            if synthetic
            else (
                "https://www.transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_"
                f"Performance_Beginning_January_2018_{year}_{number}.zip"
            ),
            "source_sha256": source_sha,
            "source_bytes": archive.stat().st_size,
            "source_member": member.filename,
            "expanded_csv_bytes": member.file_size,
            "source_columns": BTS_COLUMNS,
            "prepared_columns": LINEAGE + BTS_COLUMNS,
            "month": month,
            "rows": rows,
            "prepared_file": "prepared.csv.gz",
            "prepared_sha256": prepared_sha,
            "prepared_bytes": prepared.stat().st_size,
            "payload_sha256": payload.hexdigest(),
            "loaded_artifact_id": loaded_id,
            "csv": {
                "encoding": "utf-8",
                "delimiter": ",",
                "quote": '"',
                "line_ending": "LF",
                "empty_fields": "preserved-as-empty-string",
                "gzip_mtime": 0,
                "gzip_level": 6,
                "header": True,
            },
            "profile": {
                **{name: dict(count) for name, count in counts.items()},
                "den_rows": den_rows,
                "den_cancelled": den_cancelled,
                "den_diverted": den_diverted,
            },
        }

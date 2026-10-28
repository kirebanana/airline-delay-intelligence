"""Hand-authored SQL oracle inputs, not a production acquisition/load adapter."""

import csv
import gzip
from pathlib import Path

from test_prepare import archive

from airline_warehouse.load import build_load_plan, check_validation, read_artifact
from airline_warehouse.prepare import prepare


def fixture(directory: Path, kind="metrics") -> dict:
    if directory.exists():
        return read_artifact(directory)
    common = {
        "DestAirportID": "14771",
        "DestAirportSeqID": "1477102",
        "DOT_ID_Marketing_Airline": "19393",
        "DOT_ID_Operating_Airline": "19393",
        "Marketing_Airline_Network": "WN",
        "Operating_Airline": "WN",
        "OriginCityName": "Denver, CO",
        "DestCityName": "San Francisco, CA",
        "CRSDepTime": "2350",
    }
    if kind == "ranking":
        rows = [
            {
                **common,
                "ArrDelay": "0",
                "DepDelay": "0",
                "ArrDel15": "0",
                "DepDel15": "0",
                "DOT_ID_Marketing_Airline": "19393" if i < 99 else "19805",
                "Marketing_Airline_Network": "WN" if i < 99 else "AA",
            }
            for i in range(199)
        ]
    elif kind in ("metrics", "unknown", "invalid"):
        rows = [
            {
                **common,
                "ArrDelay": str(delay),
                "DepDelay": str(delay),
                "ArrDel15": flag,
                "DepDel15": flag,
                "DepTime": "0010",
            }
            for delay, flag in ((-10, "0"), (0, "0"), (14, "0"), (15, "1"), (60, "1"))
        ]
        reverse = {
            **common,
            "DayofMonth": "2",
            "DayOfWeek": "4",
            "FlightDate": "2025-01-02",
            "Origin": "SFO",
            "OriginAirportID": "14771",
            "OriginAirportSeqID": "1477102",
            "Dest": "DEN",
            "DestAirportID": "11292",
            "DestAirportSeqID": "1129202",
            "OriginCityName": "San Francisco, CA",
            "DestCityName": "Denver, CO",
            "DOT_ID_Marketing_Airline": "19805",
            "DOT_ID_Operating_Airline": "19805",
            "Marketing_Airline_Network": "AA",
            "Operating_Airline": "AA",
            "CRSDepTime": "0029",
        }
        rows.extend(
            [
                {**reverse, "Cancelled": "1.00", "DepTime": "1200", "DepDel15": "1"},
                {**reverse, "Diverted": "1.00", "DepDel15": "1", "ArrDelay": "999"},
                {**reverse},
                {**reverse, "ArrDel15": "0", "DepDel15": "0"},
            ]
        )
        if kind == "unknown":
            rows[0]["Cancelled"] = ""
        if kind == "invalid":
            rows[0]["ArrDelay"] = "NaN"
            rows[-1]["OriginAirportID"] = "0"
    else:
        raise ValueError("Unknown hand-authored fixture")
    directory.parent.mkdir(parents=True, exist_ok=True)
    source = directory.parent / (directory.name + "-source.zip")
    if source.exists():
        raise ValueError("Fixture source exists; inspect instead of overwrite")
    archive(source, rows)
    return prepare(source, directory, "2025-01", synthetic=True)


def load_fixture(connection, directory: Path, manifest: dict):
    if manifest["source_kind"] != "synthetic-fixture" or manifest["rows"] > 1000:
        raise ValueError("Diagnostic INSERT restricted to <=1000 synthetic test rows")
    plan = build_load_plan(manifest, "airline-bts-336805808138-us-east-2")
    with connection.cursor() as cur:
        cur.execute(plan["create_sql"])
        cur.execute(
            f"SHOW TABLES LIKE '{plan['table'].split('.')[-1]}' IN SCHEMA AIRLINE_DB.INGEST_TEST"
        )
        fields = [c[0].lower() for c in cur.description]
        existing = [dict(zip(fields, r, strict=True)) for r in cur.fetchall()]
        if len(existing) != 1 or existing[0]["comment"] != plan["table_comment"]:
            raise ValueError("Existing diagnostic object identity mismatch")
        cur.execute(f"SELECT COUNT(*) FROM {plan['table']}")
        if cur.fetchone()[0] == 0:
            with gzip.open(directory / "prepared.csv.gz", "rt", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                data = list(reader)
            columns = ", ".join('"' + name + '"' for name in header)
            cur.executemany(
                f"INSERT INTO {plan['table']} ({columns}) VALUES ("
                + ",".join(["%s"] * len(header))
                + ")",
                data,
            )
        cur.execute(plan["validation_sql"])
        check_validation(
            dict(zip([c[0] for c in cur.description], cur.fetchone(), strict=True)), manifest
        )

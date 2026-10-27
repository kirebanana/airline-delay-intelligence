"""Small explicit commands; no background jobs, cloud retries or automatic refresh."""

import argparse
import csv
import json
import sys
import zipfile
from pathlib import Path

from airline_warehouse.load import build_load_plan, execute_load, read_artifact
from airline_warehouse.prepare import PreparationError, prepare


def main(argv=None):
    parser = argparse.ArgumentParser(prog="airline")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Validate an explicit official local archive import")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--month", required=True)
    p.add_argument("--expected-sha256", required=True, help="Selected source snapshot checksum")
    p.add_argument("--synthetic", action="store_true", help="Explicitly label test fixtures")
    for name in ("plan-load", "load"):
        p = sub.add_parser(name, help="Explicit raw COPY plan or funded/controlled live execution")
        p.add_argument("--artifact", type=Path, required=True)
        p.add_argument("--bucket", required=True)
        if name == "load":
            p.add_argument(
                "--funding-verified",
                action="store_true",
                help="Attest current confirmed entitlement and covered lifecycle costs",
            )
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(
                args.archive,
                args.output,
                args.month,
                synthetic=args.synthetic,
                expected_sha256=args.expected_sha256,
            )
        else:
            manifest = read_artifact(args.artifact)
            if args.command == "plan-load":
                result = build_load_plan(manifest, args.bucket)
            else:
                if not args.funding_verified:
                    raise ValueError(
                        "Funding/entitlement must be verified before connecting to load"
                    )
                from airline_warehouse.connection import connect

                with connect() as conn:
                    result = execute_load(conn, manifest, args.bucket, funding_verified=True)
    except (PreparationError, OSError, ValueError, csv.Error, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 1
    except Exception as error:
        # Unknown client exceptions may include connection state; don't print it.
        print(
            json.dumps(
                {
                    "status": "recovery_required",
                    "error_type": type(error).__name__,
                    "message": "Inspect the exact attempt; no automatic retry was performed",
                }
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

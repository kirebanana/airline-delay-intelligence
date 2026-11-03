"""Bounded content-addressed selection and fixed-pilot dependency transport."""

import hashlib
import json
import re

from airline_warehouse.connectivity_probe import BUCKET

BTS_KEY = (
    r"manifests/prepared/bts/(202[3-5]-(?:0[1-9]|1[0-2]))/"
    r"[a-f0-9]{64}/[a-f0-9]{64}[.]json"
)
SELECTION_KEY = r"manifests/selections/([a-f0-9]{64})[.]json"


def selection_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def validate_reference(ref, pattern):
    if (
        not isinstance(ref, dict)
        or set(ref) != {"key", "sha256"}
        or not isinstance(ref["key"], str)
        or not re.fullmatch(pattern, ref["key"])
        or not isinstance(ref["sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"])
    ):
        raise ValueError("Dependency reference escapes approved immutable inputs")


def checked_bytes(s3, ref, pattern, limit):
    validate_reference(ref, pattern)
    stream = s3.get_object(Bucket=BUCKET, Key=ref["key"])["Body"]
    try:
        body = stream.read(limit + 1)
    finally:
        stream.close()
    if not body or len(body) > limit or hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise ValueError("Dependency bytes exceed bound or differ from selected checksum")
    return body


def read_selection(s3, ref):
    body = checked_bytes(s3, ref, SELECTION_KEY, 32768)
    if ref["key"] != f"manifests/selections/{ref['sha256']}.json":
        raise ValueError("Selection key must bind its exact content")
    value = json.loads(body)
    if not isinstance(value, dict) or set(value) != {"artifacts", "weather"}:
        raise ValueError("Exact artifact/weather selection required")
    refs = value["artifacts"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 36:
        raise ValueError("Select one to 36 accepted monthly artifacts")
    months = []
    for artifact in refs:
        validate_reference(artifact, BTS_KEY)
        months.append(re.fullmatch(BTS_KEY, artifact["key"])[1])
    if len(set(months)) != len(months):
        raise ValueError("Select exactly one version per month")
    if value["weather"] is not None:
        validate_weather_reference(value["weather"])
        if "2025-01" not in months:
            raise ValueError("Fixed pilot requires the selected January 2025 flight input")
    return value


def validate_weather_reference(value):
    if not isinstance(value, dict) or set(value) != {"manifest", "observations"}:
        raise ValueError("Fixed weather dependency needs manifest and observations")
    validate_reference(
        value["manifest"], r"manifests/prepared/weather/isd/72565003017/[a-f0-9]{64}[.]json"
    )
    validate_reference(
        value["observations"], r"prepared/weather/isd/72565003017/[a-f0-9]{64}/observations[.]jsonl"
    )


def restore_weather(s3, refs, directory):
    from airline_warehouse.weather import read_weather

    validate_weather_reference(refs)
    manifest = checked_bytes(
        s3,
        refs["manifest"],
        r"manifests/prepared/weather/isd/72565003017/[a-f0-9]{64}[.]json",
        16384,
    )
    value = json.loads(manifest)
    weather_id = value.get("weather_id")
    if (
        refs["manifest"]["key"] != f"manifests/prepared/weather/isd/72565003017/{weather_id}.json"
        or refs["observations"]["key"]
        != f"prepared/weather/isd/72565003017/{weather_id}/observations.jsonl"
        or refs["observations"]["sha256"] != value.get("payload_sha256")
    ):
        raise ValueError("Weather dependency identity differs from its manifest")
    payload = checked_bytes(
        s3,
        refs["observations"],
        r"prepared/weather/isd/72565003017/[a-f0-9]{64}/observations[.]jsonl",
        8 * 1024 * 1024,
    )
    directory.mkdir(exist_ok=False)
    (directory / "manifest.json").write_bytes(manifest)
    (directory / "observations.jsonl").write_bytes(payload)
    read_weather(directory)
    return directory

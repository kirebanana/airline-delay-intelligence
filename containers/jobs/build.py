"""Local allowlisted build context; never send credentials, data or state to Docker."""

import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
context = Path(tempfile.mkdtemp(prefix="airline-jobs-build-", dir="/tmp/opencode"))
files = [
    root / n for n in ("containers/jobs/Dockerfile", "containers/jobs/requirements.txt", "uv.lock")
]
files += list((root / "src/airline_warehouse").glob("*.py"))
files += [root / "src/airline_warehouse/airline_names.json"]
files += list((root / "tests").glob("*.py"))
files += [root / "sql/07_publication.sql"]
files += [root / "references/den-weather-pilot.json"]
files += [root / "references/den-ghcnh-weather-v2.json"]
files += [root / "infra/jobs/refresh.asl.json.tftpl"]
files += [root / "infra/jobs/deliver.py"]
files += [root / "infra/ingestion/delivery.tf"]
files += [root / ".github/workflows" / name for name in ("validate.yml", "release.yml")]
files += [root / ".streamlit/config.toml"]
files += [
    p
    for p in (root / "dbt").rglob("*")
    if p.is_file()
    and p.suffix in (".sql", ".yml")
    and not set(p.relative_to(root).parts) & {"target", "logs", "dbt_packages"}
]
for source in files:
    destination = context / source.relative_to(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
print("Allowlisted build context:", context, "files:", len(files), flush=True)
subprocess.run(
    [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "-f",
        str(context / "containers/jobs/Dockerfile"),
        "-t",
        "airline-jobs:local",
        str(context),
    ],
    check=True,
)

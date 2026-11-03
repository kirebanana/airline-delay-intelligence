"""Export locked Linux/amd64 requirements, resolving dbt's download-only sdist.

The dbt parser lock entry is a tiny bootstrap sdist whose backend downloads a
platform wheel. Read its hash-verified embedded asset manifest without executing
that backend, then pin the wheel URL and its embedded SHA256 explicitly.
"""

import hashlib
import io
import json
import re
import subprocess
import tarfile
import tomllib
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]
packages = tomllib.loads((root / "uv.lock").read_text())["package"]
package = next(p for p in packages if p["name"] == "dbt-core-experimental-parser")
sdist = package["sdist"]
if not sdist["url"].startswith("https://files.pythonhosted.org/"):
    raise ValueError("Unexpected locked source host")
with urllib.request.urlopen(sdist["url"], timeout=30) as response:
    body = response.read(65537)
if len(body) > 65536 or "sha256:" + hashlib.sha256(body).hexdigest() != sdist["hash"]:
    raise ValueError("Parser bootstrap source hash mismatch")
with tarfile.open(fileobj=io.BytesIO(body)) as archive:
    entries = [m for m in archive.getmembers() if m.name.endswith("/_dbt_sa_build/assets.json")]
    if len(entries) != 1:
        raise ValueError("Expected one embedded parser asset manifest")
    manifest = json.load(archive.extractfile(entries[0]))
version = package["version"]
if manifest["base_url"] != f"https://github.com/dbt-labs/dbt/releases/download/v{version}":
    raise ValueError("Unexpected parser binary release host")
wheel = manifest["wheels"]["manylinux_2_28_x86_64"]
filename = f"dbt_core_experimental_parser-{version}-py3-none-manylinux_2_28_x86_64.whl"
if wheel["filename"] != filename or not re.fullmatch(r"[a-f0-9]{64}", wheel["sha256"]):
    raise ValueError("Unexpected parser platform asset")
requirements = subprocess.check_output(
    [
        "uv",
        "export",
        "--locked",
        "--extra",
        "cloud",
        "--extra",
        "analytics",
        "--no-dev",
        "--no-emit-project",
        "--no-header",
        "--quiet",
    ],
    cwd=root,
    text=True,
)
pattern = rf"dbt-core-experimental-parser=={re.escape(version)} \\\n(?:    --hash=[^\n]+\n)+"
replacement = (
    "# Parser wheel hash comes from the hash-verified uv.lock bootstrap sdist.\n"
    f"dbt-core-experimental-parser @ {manifest['base_url']}/{filename} \\\n"
    f"    --hash=sha256:{wheel['sha256']}\n"
)
requirements, count = re.subn(pattern, lambda _: replacement, requirements)
if count != 1:
    raise ValueError("Parser requirement was not replaced exactly once")
(root / "containers/jobs/requirements.txt").write_text(requirements)
print("Exported locked Linux/amd64 requirements with verified parser wheel provenance.")

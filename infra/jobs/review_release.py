"""Review a saved release plan and hash-bind its trusted source before apply.

No apply, cloud login, task launch or secret-bearing plan output is performed.
The operator/CI must separately verify the immutable image's offline tests, scan
and runtime processing contract; this receipt is evidence, not authorization.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import airline_warehouse.cloud_workflow as graph_module
import airline_warehouse.release_plan as guard_module
from airline_warehouse.cloud_workflow import definition
from airline_warehouse.release_plan import KINDS, inspect_release_plan


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("image_manifest", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--terraform", default="terraform")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--recover-retained-deposed", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sources = [
        root / "main.tf",
        root / "refresh.asl.json.tftpl",
        Path(__file__).resolve(),
        args.image_manifest.resolve(),
        args.plan.resolve(),
        Path(graph_module.__file__).resolve(),
        Path(guard_module.__file__).resolve(),
    ]
    hashes = {str(p): digest(p) for p in sources}
    if args.verify:
        receipt = json.loads(args.receipt.read_text())
        if hashes != receipt["file_sha256"]:
            raise ValueError("Saved plan, image manifest or trusted release source changed")
        print("Reviewed saved plan and trusted release source hashes match")
        return
    image = json.loads(args.image_manifest.read_text())
    if image.get("offline_tests") != "PASS" or image.get("scan_status") != "COMPLETE":
        raise ValueError("Tested and scanned immutable image evidence required")
    plan = json.loads(
        subprocess.check_output(
            [args.terraform, "show", "-json", str(args.plan.resolve())], cwd=root
        )
    )
    review = inspect_release_plan(
        plan, image["image_digest"], allow_retained_deposed=args.recover_retained_deposed
    )
    tasks = {
        kind: f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:1"
        for kind in KINDS
    }
    text = (root / "refresh.asl.json.tftpl").read_text()
    for key, value in {
        **{"task_" + k: v for k, v in tasks.items()},
        "image_digest": image["image_digest"],
        "processing_contract": image["processing_contract"],
    }.items():
        text = text.replace("${" + key + "}", value)
    if json.loads(text) != definition(tasks, image["image_digest"], image["processing_contract"]):
        raise ValueError("Checked Terraform graph differs from tested workflow generator")
    with args.receipt.open("x") as stream:
        stream.write(json.dumps({**review, "file_sha256": hashes}, indent=2) + "\n")
    print(json.dumps(review))


if __name__ == "__main__":
    main()

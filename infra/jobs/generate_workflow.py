"""Generate the checked Terraform template from the offline-tested graph."""

import json
from pathlib import Path

from airline_warehouse.cloud_workflow import definition

tasks = {
    kind: f"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:1"
    for kind in ("acquisition", "warehouse", "publisher")
}
image = "sha256:" + "a" * 64
contract = "b" * 64
text = json.dumps(definition(tasks, image, contract), indent=2)
for kind, task in tasks.items():
    text = text.replace(task, "${task_" + kind + "}")
text = text.replace(image, "${image_digest}").replace(contract, "${processing_contract}")
Path(__file__).with_name("refresh.asl.json.tftpl").write_text(text + "\n")

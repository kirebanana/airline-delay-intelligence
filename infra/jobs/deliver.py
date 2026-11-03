"""Manual trusted GitHub delivery. Never starts a data task or refresh."""

import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-2"
ACCOUNT = "336805808138"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/airline-github-release"
REGISTRY = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com"
REPOSITORY = "airline-delay-intelligence"
IMAGE = f"{REGISTRY}/{REPOSITORY}"
WORKFLOW = f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:airline-isolated-refresh"
ROOT = Path(__file__).resolve().parents[2]


def run(*args, capture=False, **kwargs):
    return subprocess.run(
        args, cwd=ROOT, check=True, text=True, capture_output=capture, **kwargs
    ).stdout


def token(audience):
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"audience": audience})
    request = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)["value"]
    print("::add-mask::" + value, flush=True)
    return value


def assume(audience="sts.amazonaws.com"):
    return boto3.client("sts", region_name=REGION).assume_role_with_web_identity(
        RoleArn=ROLE,
        RoleSessionName="github-" + os.environ["GITHUB_RUN_ID"],
        WebIdentityToken=token(audience),
        DurationSeconds=3600,
    )


def expect_denied(operation):
    try:
        operation()
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code not in {"AccessDenied", "AccessDeniedException", "InvalidIdentityToken"}:
            raise
        return code
    raise RuntimeError("A forbidden request unexpectedly succeeded; stop qualification")


def login():
    if (
        os.environ["GITHUB_REPOSITORY"] != "kirebanana/airline-delay-intelligence"
        or os.environ["GITHUB_REF"] != "refs/heads/main"
        or os.environ["GITHUB_EVENT_NAME"] != "workflow_dispatch"
    ):
        raise ValueError("Only an explicit trusted-main dispatch may obtain release credentials")
    wrong_audience = expect_denied(lambda: assume("airline-invalid-audience"))
    credentials = assume()["Credentials"]
    names = {
        "AccessKeyId": "AWS_ACCESS_KEY_ID",
        "SecretAccessKey": "AWS_SECRET_ACCESS_KEY",
        "SessionToken": "AWS_SESSION_TOKEN",
    }
    with Path(os.environ["GITHUB_ENV"]).open("a") as stream:
        for source, destination in names.items():
            value = credentials[source]
            print("::add-mask::" + value, flush=True)
            stream.write(destination + "=" + value + "\n")
    print(
        json.dumps(
            {"trusted_environment_assumption": "PASS", "wrong_audience_denied": wrong_audience}
        )
    )


def direct_denials():
    caller = boto3.client("sts", region_name=REGION).get_caller_identity()
    if caller["Account"] != ACCOUNT or ":assumed-role/airline-github-release/" not in caller["Arn"]:
        raise ValueError("Unexpected delivery identity")
    # The role's independently reviewed explicit Deny is a prerequisite. Inputs
    # are isolated qualification requests, never production input or credentials.
    return {
        "states_start_execution": expect_denied(
            lambda: boto3.client("stepfunctions", region_name=REGION).start_execution(
                stateMachineArn=WORKFLOW,
                name="denied-github-" + os.environ["GITHUB_RUN_ID"],
                input="{}",
            )
        ),
        "ecs_run_task": expect_denied(
            lambda: boto3.client("ecs", region_name=REGION).run_task(
                cluster="airline-jobs",
                taskDefinition="airline-stage-acquisition:3",
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": ["subnet-018dbfd8d11f5e279"],
                        "securityGroups": ["sg-0c380149c18e4b13c"],
                        "assignPublicIp": "ENABLED",
                    }
                },
            )
        ),
    }


def container(image, *command, capture=False):
    return run(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "2g",
        "--entrypoint",
        "python",
        image,
        *command,
        capture=capture,
    )


def deliver(image_digest, apply, recover_partial=False):
    denials = direct_denials()
    if image_digest and not re.fullmatch(r"sha256:[a-f0-9]{64}", image_digest):
        raise ValueError("An exact immutable digest is required")
    ecr = boto3.client("ecr", region_name=REGION)
    with tempfile.TemporaryDirectory(prefix="airline-delivery-") as temporary:
        work = Path(temporary)
        os.environ["DOCKER_CONFIG"] = str(work / "docker")
        auth = ecr.get_authorization_token(registryIds=[ACCOUNT])["authorizationData"][0]
        user, password = base64.b64decode(auth["authorizationToken"]).decode().split(":", 1)
        run("docker", "login", "--username", user, "--password-stdin", REGISTRY, input=password)
        if image_digest:
            image = IMAGE + "@" + image_digest
            run("docker", "pull", image)
        else:
            run("git", "diff", "--exit-code", "HEAD")
            run("python", "containers/jobs/build.py")
            image = "airline-jobs:local"
        container(image, "-m", "unittest", "discover", "-s", "tests")
        contract = container(
            image,
            "-c",
            "from airline_warehouse.warehouse import processing_contract as c; print(c())",
            capture=True,
        ).strip()
        if not re.fullmatch(r"[a-f0-9]{64}", contract):
            raise ValueError("Invalid measured processing contract")
        if not image_digest:
            tag = "github-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
            run("docker", "tag", image, IMAGE + ":" + tag)
            run("docker", "push", IMAGE + ":" + tag)
            image_digest = ecr.describe_images(
                repositoryName=REPOSITORY, imageIds=[{"imageTag": tag}]
            )["imageDetails"][0]["imageDigest"]
        findings = None
        for _ in range(60):
            try:
                scan = ecr.describe_image_scan_findings(
                    repositoryName=REPOSITORY, imageId={"imageDigest": image_digest}
                )
            except ecr.exceptions.ScanNotFoundException:
                time.sleep(5)
                continue
            status = scan["imageScanStatus"]["status"]
            if status == "COMPLETE":
                findings = scan.get("imageScanFindings", {})
                break
            if status not in {"IN_PROGRESS", "PENDING"}:
                raise RuntimeError("Image scan did not complete successfully: " + status)
            time.sleep(5)
        if findings is None:
            raise TimeoutError("Finite image scan wait expired; do not promote")
        page_token = scan.get("nextToken")
        while page_token:
            page = ecr.describe_image_scan_findings(
                repositoryName=REPOSITORY,
                imageId={"imageDigest": image_digest},
                nextToken=page_token,
            )
            findings.setdefault("findings", []).extend(
                page.get("imageScanFindings", {}).get("findings", [])
            )
            page_token = page.get("nextToken")
        high = sorted(
            x["name"] for x in findings.get("findings", []) if x["severity"] in {"HIGH", "CRITICAL"}
        )
        reviewed = {"CVE-2026-5435", "CVE-2026-19499", "CVE-2026-85091"}
        if any(x not in reviewed for x in high) or findings.get("findingSeverityCounts", {}).get(
            "CRITICAL", 0
        ):
            raise ValueError("New HIGH/CRITICAL finding requires review before promotion")
        evidence = {
            "image_digest": image_digest,
            "processing_contract": contract,
            "offline_tests": "PASS",
            "scan_status": "COMPLETE",
            "findings": findings.get("findingSeverityCounts", {}),
            "reviewed_high_findings": high,
            "direct_launch_denials": denials,
            "source_revision": os.environ["GITHUB_SHA"],
        }
        manifest = work / "image.json"
        manifest.write_text(json.dumps(evidence))
        root = ROOT / "infra/jobs"
        plan, receipt = work / "release.tfplan", work / "receipt.json"
        run("terraform", "-chdir=" + str(root), "init", "-input=false", "-lockfile=readonly")
        run(
            "terraform",
            "-chdir=" + str(root),
            "plan",
            "-input=false",
            "-no-color",
            "-var=image_digest=" + image_digest,
            "-var=processing_contract=" + contract,
            "-out=" + str(plan),
        )
        recovery_args = ["--recover-retained-deposed"] if recover_partial else []
        run(
            "python",
            "infra/jobs/review_release.py",
            str(plan),
            str(manifest),
            str(receipt),
            *recovery_args,
        )
        run(
            "python",
            "infra/jobs/review_release.py",
            str(plan),
            str(manifest),
            str(receipt),
            "--verify",
        )
        if apply:
            run("terraform", "-chdir=" + str(root), "apply", "-input=false", "-no-color", str(plan))
            deployment = json.loads(
                run(
                    "terraform",
                    "-chdir=" + str(root),
                    "output",
                    "-json",
                    "deployment",
                    capture=True,
                )
            )
            if (
                deployment["image_digest"] != image_digest
                or deployment["processing_contract"] != contract
            ):
                raise ValueError("Deployed binding differs from qualified image")
            evidence["deployment"] = deployment
        evidence.update(applied=apply, data_launch=False)
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(
                "## Qualified code delivery\n```json\n" + json.dumps(evidence, indent=2) + "\n```\n"
            )
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["login", "deny-subject", "deliver"])
    parser.add_argument("--image-digest", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--recover-partial", action="store_true")
    args = parser.parse_args()
    if args.mode == "login":
        login()
    elif args.mode == "deny-subject":
        print(json.dumps({"untrusted_subject_denied": expect_denied(assume)}))
    else:
        deliver(args.image_digest, args.apply, args.recover_partial)

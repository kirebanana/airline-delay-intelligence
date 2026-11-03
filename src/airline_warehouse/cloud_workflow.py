"""Finite isolated tracer graph with exact task definitions and explicit S3 bridge.

Definition generation has no AWS side effects. Terraform is the sole registrar.
No redrive, automatic retry, mutation after uncertain results, or refresh on deploy.
"""

import re

BUCKET = "airline-bts-336805808138-us-east-2"
CLUSTER = "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs"
MODES = {
    "admit": "publisher",
    "acquisition": "acquisition",
    "warehouse": "warehouse",
    "publish": "publisher",
}
PREFIXES = {"publisher": "publication", "acquisition": "acquisition", "warehouse": "build"}


def definition(tasks, image_digest, processing_contract, *, extended=True):
    if (
        set(tasks) != {"acquisition", "warehouse", "publisher"}
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_digest)
        or not re.fullmatch(r"[a-f0-9]{64}", processing_contract)
    ):
        raise ValueError("Exact deployment task/image/processing identities required")
    for kind, task in tasks.items():
        if not re.fullmatch(
            rf"arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-{kind}:[1-9][0-9]*",
            task,
        ):
            raise ValueError("Unversioned or wrong-family task definition")
    states = {}
    catch = [{"ErrorEquals": ["States.ALL"], "ResultPath": "$.error", "Next": "Uncertain"}]
    carry = {
        "run.$": "$.run",
        "budget.$": "$.budget",
        "authority.$": "$.authority",
        "dependency.$": "$.dependency",
        "task.$": "$.task",
        "request.$": "$.request",
    }

    def choice(checks, next_state):
        return {
            "Type": "Choice",
            "Choices": [{"And": checks, "Next": next_state}],
            "Default": "Uncertain",
        }

    def eq(path, expected=None, other=None):
        return {
            "Variable": path,
            "StringEqualsPath" if other else "StringEquals": other or expected,
        }

    def read_object(name, key, result_path, next_state, limit=16384):
        # Only side-effect-free bridge reads retry; RunTask/SQL/claims never do.
        retry = [
            {
                "ErrorEquals": ["S3.SlowDown", "S3.ServiceUnavailable", "S3.InternalError"],
                "IntervalSeconds": 1,
                "MaxAttempts": 1,
                "BackoffRate": 1,
            }
        ]
        head = name + "Head"
        states[head] = {
            "Type": "Task",
            "Resource": "arn:aws:states:::aws-sdk:s3:headObject",
            "Parameters": {"Bucket": BUCKET, "Key.$": key},
            "ResultPath": "$.head",
            "Catch": catch,
            "Next": name + "Size",
            "TimeoutSeconds": 15,
            "Retry": retry,
        }
        states[name + "Size"] = choice(
            [
                {"Variable": "$.head.ContentLength", "NumericLessThanEquals": limit},
                {"Variable": "$.head.ContentLength", "NumericGreaterThan": 0},
            ],
            name + "Get",
        )
        states[name + "Get"] = {
            "Type": "Task",
            "Resource": "arn:aws:states:::aws-sdk:s3:getObject",
            "Parameters": {"Bucket": BUCKET, "Key.$": key},
            "ResultPath": result_path,
            "Catch": catch,
            "TimeoutSeconds": 15,
            "Retry": retry,
            "Next": next_state,
        }
        return head

    for index, (mode, kind) in enumerate(MODES.items()):
        start, run = mode + "Compose", mode + "Run"
        states[start] = {
            "Type": "Pass",
            "ResultPath": "$.request",
            "Next": run,
            "Parameters": {
                "contract": "cloud-stage-request-v2" if extended else "cloud-stage-request-v1",
                "mode": mode,
                "request_id.$": "$.run.request_id",
                "target.$": "$.run.target",
                "deadline_epoch.$": "$.run.deadlines." + mode,
                "artifacts.$": "$.run.artifacts",
                "budget.$": "$.budget",
                "authority.$": "$.authority",
                "dependency.$": "$.dependency",
                "deployment": {
                    "execution_arn.$": "$$.Execution.Id",
                    "workflow_version_arn.$": "$.run.workflow_version_arn",
                    "task_definition_arn": tasks[kind],
                    "image_digest": image_digest,
                    "processing_contract": processing_contract,
                    "attempt": 1,
                },
            },
        }
        states[run] = {
            "Type": "Task",
            "Resource": "arn:aws:states:::ecs:runTask.sync",
            "TimeoutSeconds": 2850 if kind == "warehouse" else 420,
            "Parameters": {
                "Cluster": CLUSTER,
                "TaskDefinition": tasks[kind],
                "LaunchType": "FARGATE",
                "PlatformVersion": "1.4.0",
                "ClientToken.$": f"States.Format('{{}}-{mode}', $.run.request_id)",
                "NetworkConfiguration": {
                    "AwsvpcConfiguration": {
                        "Subnets": ["subnet-018dbfd8d11f5e279"],
                        "SecurityGroups": ["sg-0c380149c18e4b13c"],
                        "AssignPublicIp": "ENABLED",
                    }
                },
                "Overrides": {
                    "ContainerOverrides": [
                        {
                            "Name": "job",
                            "Environment": [
                                {
                                    "Name": "AIRLINE_STAGE_REQUEST",
                                    "Value.$": "States.JsonToString($.request)",
                                },
                            ],
                        }
                    ]
                },
            },
            "ResultSelector": {
                "arn.$": "$.TaskArn",
                "definition.$": "$.TaskDefinitionArn",
                "exit.$": "$.Containers[0].ExitCode",
                "image.$": "$.Containers[0].ImageDigest",
            },
            "ResultPath": "$.task",
            "Catch": catch,
            "Next": mode + "CheckExit",
        }
        key = f"States.Format('reports/{PREFIXES[kind]}/{{}}/{mode}.json', $.run.request_id)"
        control_head = read_object(mode + "Control", key, "$.raw_control", mode + "DecodeControl")
        states[mode + "CheckExit"] = choice(
            [
                {"Variable": "$.task.exit", "NumericEquals": 0},
                eq("$.task.definition", tasks[kind]),
                eq("$.task.image", image_digest),
            ],
            control_head,
        )
        states[mode + "DecodeControl"] = {
            "Type": "Pass",
            "Next": mode + "CheckControl",
            "Parameters": {
                **carry,
                "control.$": "States.StringToJson($.raw_control.Body)",
                "inputs_expected.$": "$.run.inputs_sha256"
                if extended
                else "States.JsonToString($.run.inputs)",
            },
        }
        # Scalar bindings are checked against the independent .sync response and
        # pinned deployment. Input maps get a separate canonical-string check.
        states[mode + "CheckControl"] = choice(
            [
                eq("$.control.contract", "ecs-stage-result-v1"),
                eq("$.control.status", "COMPLETED"),
                eq("$.control.request_id", other="$.run.request_id"),
                eq("$.control.target", other="$.run.target"),
                eq("$.control.stage", kind),
                eq("$.control.task_arn", other="$.task.arn"),
                eq("$.control.task_definition_arn", tasks[kind]),
                eq("$.control.image_digest", image_digest),
                eq("$.control.processing_contract", processing_contract),
                eq("$.control.execution_arn", other="$.request.deployment.execution_arn"),
                eq("$.control.workflow_version_arn", other="$.run.workflow_version_arn"),
                {"Variable": "$.control.attempt", "NumericEquals": 1},
                {
                    "Variable": "$.control.deadline_epoch",
                    "NumericEqualsPath": "$.request.deadline_epoch",
                },
                {
                    "Variable": "$.control.completed_epoch",
                    "NumericLessThanEqualsPath": "$.request.deadline_epoch",
                },
            ],
            mode + "PrepareReport",
        )
        states[mode + "PrepareReport"] = {
            "Type": "Pass",
            "Next": mode + "CheckReference",
            "Parameters": {
                **carry,
                "control.$": "$.control",
                "inputs_expected.$": "$.inputs_expected",
                "inputs_actual.$": "$.control.inputs_sha256"
                if extended
                else "States.JsonToString($.control.inputs)",
                "expected_report.$": (
                    f"States.Format('reports/{PREFIXES[kind]}/{{}}/{mode}-report.json', "
                    "$.run.request_id)"
                ),
            },
        }
        report_head = read_object(
            mode + "Report",
            "$.control.output.key",
            "$.raw_report",
            mode + "HashReport",
            limit=10000,
        )
        states[mode + "CheckReference"] = choice(
            [
                eq("$.control.output.key", other="$.expected_report"),
                eq("$.inputs_actual", other="$.inputs_expected"),
            ],
            report_head,
        )
        states[mode + "HashReport"] = {
            "Type": "Pass",
            "ResultPath": "$.hash",
            "Next": mode + "CheckHash",
            "Parameters": {"actual.$": "States.Hash($.raw_report.Body, 'SHA-256')"},
        }
        states[mode + "CheckHash"] = choice(
            [
                eq("$.hash.actual", other="$.control.output.sha256"),
            ],
            mode + "DecodeReport",
        )
        states[mode + "DecodeReport"] = {
            "Type": "Pass",
            "Next": mode + "CheckReport",
            "Parameters": {
                **carry,
                "control.$": "$.control",
                "stage.$": "States.StringToJson($.raw_report.Body)",
            },
        }
        states[mode + "CheckReport"] = choice(
            [
                eq("$.stage.status", "COMPLETED"),
                eq("$.stage.mode", mode),
                eq("$.stage.request_id", other="$.run.request_id"),
                eq("$.stage.target", other="$.run.target"),
            ],
            mode + "Advance",
        )
        if mode == "publish":
            states[mode + "Advance"] = {"Type": "Pass", "InputPath": "$.stage", "End": True}
        else:
            next_mode = list(MODES)[index + 1]
            states[mode + "Advance"] = {
                "Type": "Pass",
                "Next": next_mode + "Compose",
                "Parameters": {
                    "run.$": "$.run",
                    "budget.$": "$.stage.budget",
                    "authority.$": "$.stage.authority" if mode == "admit" else "$.authority",
                    "dependency.$": "$.control.output" if mode == "warehouse" else "$.dependency",
                },
            }
        if extended and mode == "admit":
            states[mode + "CheckReport"]["Choices"][0]["Next"] = "admitOutcome"
    if extended:
        states["admitOutcome"] = {
            "Type": "Choice",
            "Choices": [
                {"Variable": "$.stage.reused", "BooleanEquals": True, "Next": "ReplayComplete"}
            ],
            "Default": "admitAdvance",
        }
        states["ReplayComplete"] = {"Type": "Pass", "InputPath": "$.stage", "End": True}
    states["Uncertain"] = {
        "Type": "Fail",
        "Error": "RECOVERY_REQUIRED",
        "Cause": "No retry/takeover: reconcile this execution, task and query evidence",
    }
    states["Initialize"] = {
        "Type": "Pass",
        "Next": "admitCompose",
        "Parameters": {
            "run.$": "$.run",
            "budget.$": "$.run.budget",
            "authority": None,
            "dependency": None,
        },
    }
    return {"StartAt": "Initialize", "TimeoutSeconds": 3600, "States": states}

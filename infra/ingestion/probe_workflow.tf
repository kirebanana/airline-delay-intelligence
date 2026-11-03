resource "aws_iam_role" "probe_workflow" {
  name = "airline-probe-workflow"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole"
      Principal = { Service = "states.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = "336805808138" }
        ArnEquals    = { "aws:SourceArn" = "arn:aws:states:us-east-2:336805808138:stateMachine:airline-connectivity-qualification" }
      }
    }]
  })
  tags = { Scope = "connectivity-16" }
}

resource "aws_iam_role_policy" "probe_workflow" {
  name = "airline-probe-sync-and-small-report"
  role = aws_iam_role.probe_workflow.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Action = "ecs:RunTask"
        Resource  = aws_ecs_task_definition.probe["warehouse"].arn
        Condition = { ArnEquals = { "ecs:cluster" = aws_ecs_cluster.jobs.arn } }
      },
      {
        Effect   = "Allow", Action = ["ecs:DescribeTasks", "ecs:StopTask"]
        Resource = "arn:aws:ecs:us-east-2:336805808138:task/airline-jobs/*"
      },
      {
        Effect    = "Allow", Action = "iam:PassRole"
        Resource  = [aws_iam_role.job["warehouse"].arn, aws_iam_role.execution.arn]
        Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } }
      },
      {
        Effect   = "Allow", Action = ["events:PutTargets", "events:PutRule", "events:DescribeRule"]
        Resource = "arn:aws:events:us-east-2:336805808138:rule/StepFunctionsGetEventsForECSTaskRule"
      },
      {
        Effect   = "Allow", Action = "s3:GetObject"
        Resource = "${aws_s3_bucket.bts.arn}/reports/build/*/connectivity.json"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "probe" {
  name       = "airline-connectivity-qualification"
  role_arn   = aws_iam_role.probe_workflow.arn
  type       = "STANDARD"
  publish    = true
  definition = file("${path.module}/probe-workflow.asl.json")
  tags       = { Scope = "connectivity-16" }
  depends_on = [aws_iam_role_policy.probe_workflow]
  lifecycle { prevent_destroy = true }
}

output "probe_workflow_version" {
  value = aws_sfn_state_machine.probe.state_machine_version_arn
}

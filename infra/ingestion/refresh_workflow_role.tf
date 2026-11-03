# Platform-owned permissions. The application-release root cannot change these.
resource "aws_iam_role" "refresh_workflow" {
  name = "airline-refresh-workflow"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "states.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = "336805808138" }
        ArnEquals    = { "aws:SourceArn" = "arn:aws:states:us-east-2:336805808138:stateMachine:airline-isolated-refresh" }
      }
    }]
  })
  tags = { Scope = "workflow-16" }
}
resource "aws_iam_role_policy" "refresh_workflow" {
  name = "airline-finite-refresh-sync-and-reports"
  role = aws_iam_role.refresh_workflow.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Action = "ecs:RunTask"
        Resource  = [for kind in ["acquisition", "warehouse", "publisher"] : "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-${kind}:*"]
        Condition = { ArnEquals = { "ecs:cluster" = aws_ecs_cluster.jobs.arn } }
      },
      {
        Effect   = "Allow", Action = ["ecs:DescribeTasks", "ecs:StopTask"]
        Resource = "arn:aws:ecs:us-east-2:336805808138:task/airline-jobs/*"
      },
      {
        Effect    = "Allow", Action = "iam:PassRole"
        Resource  = concat([for role in aws_iam_role.job : role.arn], [aws_iam_role.execution.arn])
        Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } }
      },
      {
        Effect   = "Allow", Action = ["events:PutTargets", "events:PutRule", "events:DescribeRule"]
        Resource = "arn:aws:events:us-east-2:336805808138:rule/StepFunctionsGetEventsForECSTaskRule"
      },
      {
        Effect   = "Allow", Action = "s3:GetObject"
        Resource = [for prefix in ["acquisition", "build", "publication"] : "${aws_s3_bucket.bts.arn}/reports/${prefix}/*"]
      }
    ]
  })
}

# Explicit finite failure qualification only; never referenced by refresh/deploy.
# One exact isolated guard transaction + fixed 120s read, then intentional exit31.
resource "aws_ecs_task_definition" "transaction_probe" {
  family                   = "airline-transaction-qualification"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "1024"
  task_role_arn            = aws_iam_role.job["publisher"].arn
  execution_role_arn       = aws_iam_role.execution.arn
  skip_destroy             = true
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "scratch" }
  container_definitions = jsonencode([{
    name            = "job", essential = true, user = "65532:65532", readonlyRootFilesystem = true
    image           = "${aws_ecr_repository.jobs.repository_url}@sha256:651adf5faae51838dc8a9f85a87ff623e1af6c4e4a6fcdc1888f79d7931458e3"
    entryPoint      = ["python", "-m", "airline_warehouse.transaction_probe"]
    environment     = [{ name = "AIRLINE_CLOUD_IDENTITY", value = "publisher" }]
    mountPoints     = [{ sourceVolume = "scratch", containerPath = "/work", readOnly = false }]
    portMappings    = [], systemControls = [], volumesFrom = [], stopTimeout = 30
    linuxParameters = { capabilities = { add = [], drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = aws_cloudwatch_log_group.jobs.name
        "awslogs-region" = "us-east-2", "awslogs-stream-prefix" = "transaction-probe"
      }
    }
  }])
  tags = { Scope = "attended-recovery-qualification-18" }
  lifecycle { prevent_destroy = true }
}

output "transaction_probe_task" {
  value = { task_definition_arn = aws_ecs_task_definition.transaction_probe.arn }
}

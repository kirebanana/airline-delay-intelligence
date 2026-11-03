# Read-only authentication/result-transfer qualification; no data refresh.
resource "aws_ecs_task_definition" "auth_probe" {
  for_each                 = toset(["warehouse", "publisher"])
  family                   = "airline-auth-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "1024"
  task_role_arn            = aws_iam_role.job[each.key].arn
  execution_role_arn       = aws_iam_role.execution.arn
  skip_destroy             = true
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name            = "job", essential = true, user = "65532:65532", readonlyRootFilesystem = true
    image           = "${aws_ecr_repository.jobs.repository_url}@sha256:14016f9bd7d06bfc8c012fc7af193e257ae0e4048cde4a5cc3a8062230acc4ea"
    environment     = [{ name = "AIRLINE_CLOUD_IDENTITY", value = each.key }]
    mountPoints     = [], portMappings = [], systemControls = [], volumesFrom = []
    stopTimeout     = 30
    linuxParameters = { capabilities = { add = [], drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = aws_cloudwatch_log_group.jobs.name
        "awslogs-region" = "us-east-2", "awslogs-stream-prefix" = "auth-${each.key}"
      }
    }
  }])
  tags = { Scope = "authentication-16" }
}

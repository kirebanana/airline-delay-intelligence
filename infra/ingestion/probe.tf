# Secret-free connectivity qualification; no service or automatic task launch.
locals {
  probe_image = "${aws_ecr_repository.jobs.repository_url}@sha256:8b55c94319958efe27beb55852d37295e64950a6d939dfb12dc81c5131385a48"
}

resource "aws_ecs_cluster" "jobs" {
  name = "airline-jobs"
  tags = { Scope = "finite-jobs-16" }
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_task_definition" "probe" {
  for_each                 = local.job_roles
  family                   = "airline-probe-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  task_role_arn            = aws_iam_role.job[each.key].arn
  execution_role_arn       = aws_iam_role.execution.arn
  skip_destroy             = true
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name            = "job", image = local.probe_image, essential = true
    user            = "65532:65532", readonlyRootFilesystem = true
    stopTimeout     = 30
    environment     = [], mountPoints = [], portMappings = [], systemControls = [], volumesFrom = []
    linuxParameters = { capabilities = { add = [], drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.jobs.name
        "awslogs-region"        = "us-east-2"
        "awslogs-stream-prefix" = "probe-${each.key}"
      }
    }
  }])
  tags = { Scope = "connectivity-16" }
}

output "connectivity_probe" {
  value = {
    cluster_arn = aws_ecs_cluster.jobs.arn
    image       = local.probe_image
    tasks       = { for kind, task in aws_ecs_task_definition.probe : kind => task.arn }
  }
}

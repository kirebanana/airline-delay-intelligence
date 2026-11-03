terraform {
  required_version = ">= 1.13.4, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.33.0" }
  }
  backend "s3" {
    bucket              = "airline-state-336805808138-us-east-2"
    key                 = "aws/jobs.tfstate"
    region              = "us-east-2"
    allowed_account_ids = ["336805808138"]
    encrypt             = true
    use_lockfile        = true
  }
}

variable "aws_profile" {
  type    = string
  default = null
}
variable "image_digest" {
  type = string
  validation {
    condition     = can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
    error_message = "A tested immutable ECR image digest is required."
  }
}
variable "processing_contract" {
  type = string
  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.processing_contract))
    error_message = "Exact image processing-contract hash required."
  }
}
provider "aws" {
  region              = "us-east-2"
  profile             = var.aws_profile
  allowed_account_ids = ["336805808138"]
  default_tags { tags = { Project = "airline-delay-intelligence", ManagedBy = "terraform", Scope = "release-16" } }
}

resource "aws_ecs_task_definition" "stage" {
  for_each                 = toset(["acquisition", "warehouse", "publisher"])
  family                   = "airline-stage-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.key == "warehouse" ? "512" : "256"
  memory                   = each.key == "warehouse" ? "2048" : "1024"
  task_role_arn            = "arn:aws:iam::336805808138:role/airline-job-${each.key}"
  execution_role_arn       = "arn:aws:iam::336805808138:role/airline-job-execution"
  skip_destroy             = true
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "scratch" }
  container_definitions = jsonencode([{
    name            = "job", essential = true, user = "65532:65532", readonlyRootFilesystem = true
    image           = "336805808138.dkr.ecr.us-east-2.amazonaws.com/airline-delay-intelligence@${var.image_digest}"
    environment     = [{ name = "AIRLINE_CLOUD_IDENTITY", value = each.key }]
    mountPoints     = [{ sourceVolume = "scratch", containerPath = "/work", readOnly = false }]
    portMappings    = [], systemControls = [], volumesFrom = [], stopTimeout = 30
    linuxParameters = { capabilities = { add = [], drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = "/airline-delay-intelligence/jobs"
        "awslogs-region" = "us-east-2", "awslogs-stream-prefix" = "stage-${each.key}"
      }
    }
  }])
  lifecycle { create_before_destroy = true }
}

resource "aws_sfn_state_machine" "refresh" {
  name     = "airline-isolated-refresh"
  role_arn = "arn:aws:iam::336805808138:role/airline-refresh-workflow"
  type     = "STANDARD"
  publish  = true
  definition = templatefile("${path.module}/refresh.asl.json.tftpl", {
    task_acquisition    = aws_ecs_task_definition.stage["acquisition"].arn
    task_warehouse      = aws_ecs_task_definition.stage["warehouse"].arn
    task_publisher      = aws_ecs_task_definition.stage["publisher"].arn
    image_digest        = var.image_digest
    processing_contract = var.processing_contract
  })
  lifecycle { prevent_destroy = true }
}

output "deployment" {
  value = {
    account              = "336805808138", region = "us-east-2"
    image_digest         = var.image_digest, processing_contract = var.processing_contract
    tasks                = { for kind, task in aws_ecs_task_definition.stage : kind => task.arn }
    workflow_version_arn = aws_sfn_state_machine.refresh.state_machine_version_arn
  }
}

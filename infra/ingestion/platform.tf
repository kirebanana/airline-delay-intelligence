# Ticket15 preparation only. No tasks, executions, schedules or secret values.
# The existing seven ingestion resources retain their names, addresses and owner.
locals {
  state_bucket = "airline-state-336805808138-us-east-2"
  state_keys   = ["aws/ingestion.tfstate", "snowflake/static.tfstate"]
  job_tags     = { Scope = "platform-15" }
  job_roles    = toset(["acquisition", "warehouse", "publisher"])
  job_role_arns = [for name in ["acquisition", "warehouse", "publisher", "execution"] :
    "arn:aws:iam::336805808138:role/airline-job-${name}"
  ]
  task_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = "336805808138" }
        ArnLike      = { "aws:SourceArn" = "arn:aws:ecs:us-east-2:336805808138:*" }
      }
    }]
  })
  read_prefixes = {
    acquisition = ["original/bts/*", "prepared/bts/*", "manifests/*", "reports/acquisition/*"]
    warehouse   = ["prepared/*", "manifests/*", "reports/acquisition/*", "reports/build/*"]
    publisher   = ["prepared/*", "manifests/*", "reports/build/*", "reports/publication/*"]
  }
  write_prefixes = {
    acquisition = ["original/bts/*", "prepared/bts/*", "manifests/prepared/bts/*", "manifests/retrieval/bts/*", "reports/acquisition/*"]
    warehouse   = ["reports/build/*"]
    publisher   = ["reports/publication/*"]
  }
}

resource "aws_s3_bucket" "state" {
  bucket        = local.state_bucket
  force_destroy = false
  tags          = local.job_tags
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    blocked_encryption_types = ["SSE-C"]
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*"
        Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "DenyJobStateAccess", Effect = "Deny", Principal = "*", Action = "s3:*"
        Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
        Condition = { ArnEquals = { "aws:PrincipalArn" = local.job_role_arns } }
      }
    ]
  })
  depends_on = [aws_s3_bucket_public_access_block.state]
}

resource "aws_iam_role_policy" "operator_state" {
  name = "airline-project-state-and-locks"
  role = "airline-project-dev"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = [aws_s3_bucket.state.arn]
      },
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = [aws_s3_bucket.state.arn]
        Condition = { StringEquals = { "s3:prefix" = concat(local.state_keys, [for key in local.state_keys : "${key}.tflock"]) } }
      },
      {
        Effect   = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
        Resource = [for key in local.state_keys : "${aws_s3_bucket.state.arn}/${key}"]
      },
      {
        Effect   = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [for key in local.state_keys : "${aws_s3_bucket.state.arn}/${key}.tflock"]
      }
    ]
  })
}

resource "aws_vpc" "jobs" {
  cidr_block           = "10.64.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.job_tags, { Name = "airline-jobs" })
}

resource "aws_subnet" "jobs" {
  vpc_id                  = aws_vpc.jobs.id
  cidr_block              = "10.64.0.0/24"
  availability_zone       = "us-east-2a"
  map_public_ip_on_launch = false
  tags                    = merge(local.job_tags, { Name = "airline-finite-jobs" })
}

resource "aws_internet_gateway" "jobs" {
  vpc_id = aws_vpc.jobs.id
  tags   = local.job_tags
}

resource "aws_route_table" "jobs" {
  vpc_id = aws_vpc.jobs.id
  tags   = local.job_tags
}

resource "aws_route" "jobs_internet" {
  route_table_id         = aws_route_table.jobs.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.jobs.id
}

resource "aws_route_table_association" "jobs" {
  subnet_id      = aws_subnet.jobs.id
  route_table_id = aws_route_table.jobs.id
}

resource "aws_security_group" "jobs" {
  name        = "airline-jobs-no-inbound"
  description = "No inbound; HTTPS services and HTTP certificate revocation checks only."
  vpc_id      = aws_vpc.jobs.id
  tags        = local.job_tags
}

resource "aws_vpc_security_group_egress_rule" "jobs" {
  for_each          = { https = 443, certificate_status = 80 }
  security_group_id = aws_security_group.jobs.id
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
  cidr_ipv4         = "0.0.0.0/0"
  description       = each.key == "https" ? "AWS/BTS/NOAA/Snowflake TLS" : "Snowflake OCSP/CRL; no customer payloads"
  tags              = local.job_tags
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.jobs.id
  service_name      = "com.amazonaws.us-east-2.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.jobs.id]
  tags              = local.job_tags
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ProjectBucketOnly", Effect = "Allow", Principal = "*"
        Action    = ["s3:GetBucketLocation", "s3:ListBucket", "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
        Resource  = [aws_s3_bucket.bts.arn, "${aws_s3_bucket.bts.arn}/*"]
        Condition = { ArnEquals = { "aws:PrincipalArn" = [for role in aws_iam_role.job : role.arn] } }
      },
      {
        # ECR returns signed S3 URLs for image layers. A project-bucket-only
        # endpoint policy would block image pulls even with ECR IAM permission.
        Sid      = "RegionalEcrLayers", Effect = "Allow", Principal = "*"
        Action   = ["s3:GetObject"]
        Resource = ["arn:aws:s3:::prod-us-east-2-starport-layer-bucket/*"]
      }
    ]
  })
}

resource "aws_ecr_repository" "jobs" {
  name                 = "airline-delay-intelligence"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  tags                 = local.job_tags
  encryption_configuration { encryption_type = "AES256" }
  image_scanning_configuration { scan_on_push = true }
  lifecycle { prevent_destroy = true }
  # No age/count lifecycle rule: retained task revisions may still reference images.
}

resource "aws_cloudwatch_log_group" "jobs" {
  name              = "/airline-delay-intelligence/jobs"
  retention_in_days = 30
  tags              = local.job_tags
}

resource "aws_secretsmanager_secret" "snowflake" {
  for_each                = toset(["warehouse", "publisher"])
  name                    = "airline-delay-intelligence/snowflake/${each.key}"
  description             = "Protected out-of-band workload credential; Terraform manages metadata only."
  recovery_window_in_days = 30
  tags                    = local.job_tags
  lifecycle { prevent_destroy = true }
  # Never add aws_secretsmanager_secret_version or a secret_string here.
}

resource "aws_iam_role" "job" {
  for_each           = local.job_roles
  name               = "airline-job-${each.key}"
  assume_role_policy = local.task_trust
  tags               = local.job_tags
}

resource "aws_iam_role_policy" "job" {
  for_each = local.job_roles
  name     = "airline-${each.key}-objects-and-own-secret"
  role     = aws_iam_role.job[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = [aws_s3_bucket.bts.arn]
      },
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = [aws_s3_bucket.bts.arn]
        Condition = { StringLike = { "s3:prefix" = distinct(concat(local.read_prefixes[each.key], local.write_prefixes[each.key])) } }
      },
      {
        Effect   = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = [for prefix in local.read_prefixes[each.key] : "${aws_s3_bucket.bts.arn}/${prefix}"]
      },
      {
        Effect   = "Allow", Action = ["s3:PutObject"]
        Resource = [for prefix in local.write_prefixes[each.key] : "${aws_s3_bucket.bts.arn}/${prefix}"]
        Condition = {
          StringEquals = { "s3:x-amz-server-side-encryption" = "AES256" }
          Null         = { "s3:if-none-match" = "false" }
        }
      }
      ], each.key == "acquisition" ? [] : [{
        Effect   = "Allow", Action = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.snowflake[each.key].arn]
    }])
  })
}

resource "aws_iam_role" "execution" {
  name               = "airline-job-execution"
  assume_role_policy = local.task_trust
  tags               = local.job_tags
}

resource "aws_iam_role_policy" "execution" {
  name = "airline-ecr-pull-and-log-delivery"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # GetAuthorizationToken has no resource-level IAM restriction. Pull APIs do.
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = ["*"] },
      {
        Effect   = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
        Resource = [aws_ecr_repository.jobs.arn]
      },
      {
        Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.jobs.arn}:*"]
      }
    ]
  })
}

output "job_preparation" {
  value = {
    subnet_id          = aws_subnet.jobs.id
    security_group_id  = aws_security_group.jobs.id
    repository_url     = aws_ecr_repository.jobs.repository_url
    execution_role_arn = aws_iam_role.execution.arn
    task_role_arns     = { for name, role in aws_iam_role.job : name => role.arn }
    secret_arns        = { for name, secret in aws_secretsmanager_secret.snowflake : name => secret.arn }
    log_group          = aws_cloudwatch_log_group.jobs.name
    state_bucket       = aws_s3_bucket.state.id
  }
}

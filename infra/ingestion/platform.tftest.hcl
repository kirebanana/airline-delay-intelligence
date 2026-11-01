mock_provider "aws" {
  override_during = plan
}

override_resource {
  target          = aws_s3_bucket.bts
  override_during = plan
  values          = { arn = "arn:aws:s3:::airline-bts-336805808138-us-east-2", id = "airline-bts-336805808138-us-east-2" }
}
override_resource {
  target          = aws_s3_bucket.state
  override_during = plan
  values          = { arn = "arn:aws:s3:::airline-state-336805808138-us-east-2", id = "airline-state-336805808138-us-east-2" }
}
override_resource {
  target          = aws_secretsmanager_secret.snowflake["warehouse"]
  override_during = plan
  values          = { arn = "arn:aws:secretsmanager:us-east-2:336805808138:secret:warehouse-example" }
}
override_resource {
  target          = aws_secretsmanager_secret.snowflake["publisher"]
  override_during = plan
  values          = { arn = "arn:aws:secretsmanager:us-east-2:336805808138:secret:publisher-example" }
}

override_resource {
  target          = aws_security_group.jobs
  override_during = plan
  values          = { ingress = [] }
}

override_resource {
  target          = aws_iam_role.job["acquisition"]
  override_during = plan
  values          = { arn = "arn:aws:iam::336805808138:role/airline-job-acquisition" }
}
override_resource {
  target          = aws_iam_role.job["warehouse"]
  override_during = plan
  values          = { arn = "arn:aws:iam::336805808138:role/airline-job-warehouse" }
}
override_resource {
  target          = aws_iam_role.job["publisher"]
  override_during = plan
  values          = { arn = "arn:aws:iam::336805808138:role/airline-job-publisher" }
}
override_resource {
  target          = aws_ecr_repository.jobs
  override_during = plan
  values          = { arn = "arn:aws:ecr:us-east-2:336805808138:repository/airline-delay-intelligence" }
}
override_resource {
  target          = aws_cloudwatch_log_group.jobs
  override_during = plan
  values          = { arn = "arn:aws:logs:us-east-2:336805808138:log-group:/airline-delay-intelligence/jobs" }
}

run "minimal_network_and_private_versioned_state" {
  command = plan
  variables {
    funding_verified        = true
    snowflake_principal_arn = null
    snowflake_external_id   = null
  }
  assert {
    condition     = aws_vpc.jobs.cidr_block == "10.64.0.0/16" && aws_subnet.jobs.cidr_block == "10.64.0.0/24" && !aws_subnet.jobs.map_public_ip_on_launch
    error_message = "Use the dedicated network; public IPs are later explicit task settings, not subnet defaults."
  }
  assert {
    condition     = length(aws_security_group.jobs.ingress) == 0 && toset([for rule in aws_vpc_security_group_egress_rule.jobs : rule.to_port]) == toset([80, 443])
    error_message = "No inbound rule or unrestricted port range; retain TLS and OCSP/CRL connectivity."
  }
  assert {
    condition     = aws_s3_bucket.state.bucket != aws_s3_bucket.bts.bucket && !aws_s3_bucket.state.force_destroy && aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled" && aws_s3_bucket_public_access_block.state.block_public_policy
    error_message = "State must be separate, private, versioned and not force-deletable."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.state.policy).Statement[1].Condition.ArnEquals["aws:PrincipalArn"] == local.job_role_arns
    error_message = "All workload/execution roles must be explicitly denied state access."
  }
  assert {
    condition     = jsondecode(aws_vpc_endpoint.s3.policy).Statement[1].Resource == ["arn:aws:s3:::prod-us-east-2-starport-layer-bucket/*"] && jsondecode(aws_vpc_endpoint.s3.policy).Statement[1].Action == ["s3:GetObject"]
    error_message = "The only non-project S3 exception is signed Ohio ECR image-layer GET access."
  }
}

run "workload_credentials_and_state_lock_permissions_are_separate" {
  command = plan
  variables {
    funding_verified        = true
    snowflake_principal_arn = null
    snowflake_external_id   = null
  }
  assert {
    condition     = length(jsondecode(aws_iam_role_policy.job["acquisition"].policy).Statement) == 4 && length(jsondecode(aws_iam_role_policy.execution.policy).Statement) == 3
    error_message = "Acquisition and execution roles must not inherit Snowflake secret access."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.job["warehouse"].policy).Statement[4].Resource == [aws_secretsmanager_secret.snowflake["warehouse"].arn] && jsondecode(aws_iam_role_policy.job["publisher"].policy).Statement[4].Resource == [aws_secretsmanager_secret.snowflake["publisher"].arn]
    error_message = "Each Snowflake workload may retrieve only its own credential."
  }
  assert {
    condition     = alltrue([for role in aws_iam_role.job : jsondecode(role.assume_role_policy).Statement[0].Principal.Service == "ecs-tasks.amazonaws.com" && jsondecode(role.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "336805808138"])
    error_message = "Task trust must be service/account constrained, not a wildcard principal."
  }
  assert {
    condition     = alltrue([for policy in aws_iam_role_policy.job : jsondecode(policy.policy).Statement[3].Condition.Null["s3:if-none-match"] == "false" && jsondecode(policy.policy).Statement[3].Condition.StringEquals["s3:x-amz-server-side-encryption"] == "AES256"])
    error_message = "Output writers must use conditional encrypted puts; no silent overwrite."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.operator_state.policy).Statement[3].Action == ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"] && alltrue([for arn in jsondecode(aws_iam_role_policy.operator_state.policy).Statement[3].Resource : endswith(arn, ".tflock")]) && !contains(jsondecode(aws_iam_role_policy.operator_state.policy).Statement[2].Action, "s3:DeleteObject")
    error_message = "Lock cleanup must never grant deletion of the actual state object or versions."
  }
  assert {
    condition     = aws_ecr_repository.jobs.image_tag_mutability == "IMMUTABLE" && !aws_ecr_repository.jobs.force_delete && aws_cloudwatch_log_group.jobs.retention_in_days == 30 && length(aws_secretsmanager_secret.snowflake) == 2
    error_message = "Retain immutable images, bounded logs and metadata-only credential objects."
  }
}

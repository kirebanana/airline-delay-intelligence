mock_provider "aws" {}

run "unverified_funding_blocks_creation" {
  command         = plan
  expect_failures = [aws_s3_bucket.bts]
}

run "private_minimal_storage_and_closed_initial_trust" {
  command = plan
  variables {
    funding_verified = true
  }
  assert {
    condition     = aws_s3_bucket.bts.force_destroy == false && aws_s3_bucket_public_access_block.bts.block_public_policy && aws_s3_bucket_public_access_block.bts.block_public_acls && aws_s3_bucket_public_access_block.bts.ignore_public_acls && aws_s3_bucket_public_access_block.bts.restrict_public_buckets
    error_message = "Storage must remain private and cannot be emptied by destroy."
  }
  assert {
    condition     = jsondecode(aws_iam_role.snowflake.assume_role_policy).Statement[0].Effect == "Deny"
    error_message = "Initial Snowflake trust must be nonfunctional, not trust account root."
  }
  assert {
    condition     = aws_s3_bucket_ownership_controls.bts.rule[0].object_ownership == "BucketOwnerEnforced"
    error_message = "Object ACLs must be disabled."
  }
  assert {
    condition     = contains(one(aws_s3_bucket_server_side_encryption_configuration.bts.rule).blocked_encryption_types, "SSE-C")
    error_message = "Preserve AWS's default block on customer-provided encryption keys."
  }
}

run "only_generated_identity_can_read_prepared" {
  command = plan
  variables {
    funding_verified        = true
    snowflake_principal_arn = "arn:aws:iam::123456789012:user/generated-test-identity"
    snowflake_external_id   = "test-generated-external-id"
  }
  assert {
    condition     = jsondecode(aws_iam_role.snowflake.assume_role_policy).Statement[0].Principal.AWS == var.snowflake_principal_arn && jsondecode(aws_iam_role.snowflake.assume_role_policy).Statement[0].Condition.StringEquals["sts:ExternalId"] == var.snowflake_external_id
    error_message = "Trust must bind both exact generated identity and external ID."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.read_prepared.policy).Statement[2].Action == ["s3:GetObject", "s3:GetObjectVersion"]
    error_message = "Snowflake cannot upload, delete, administer or read other prefixes."
  }
}

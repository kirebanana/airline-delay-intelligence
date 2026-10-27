variable "funding_verified" {
  type        = bool
  default     = false
  description = "Set only after current S3 credit applicability/expiry and lifecycle coverage are confirmed."
}

variable "snowflake_principal_arn" {
  type        = string
  default     = null
  description = "Exact STORAGE_AWS_IAM_USER_ARN from DESC INTEGRATION; null keeps trust closed."
  validation {
    condition     = var.snowflake_principal_arn == null ? true : can(regex("^arn:aws:iam::[0-9]{12}:user/[A-Za-z0-9+=,.@_/-]+$", var.snowflake_principal_arn))
    error_message = "Use the generated Snowflake IAM user ARN, not account root or a wildcard."
  }
}

variable "snowflake_external_id" {
  type        = string
  default     = null
  description = "Exact STORAGE_AWS_EXTERNAL_ID; an integration identifier, not an AWS credential."
  validation {
    condition     = var.snowflake_external_id == null ? true : length(var.snowflake_external_id) > 5
    error_message = "Use the actual generated external ID, never an empty placeholder."
  }
}

locals {
  bucket = "airline-bts-336805808138-us-east-2"
  trust = var.snowflake_principal_arn == null ? jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Deny", Action = "sts:AssumeRole", Principal = { AWS = "*" }
    }]
    }) : jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole",
      Principal = { AWS = var.snowflake_principal_arn },
      Condition = { StringEquals = { "sts:ExternalId" = var.snowflake_external_id } }
    }]
  })
}

resource "aws_s3_bucket" "bts" {
  bucket        = local.bucket
  force_destroy = false
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.funding_verified
      error_message = "STOP: paid-account credit/expiry/service and lifecycle coverage are not verified."
    }
  }
}

resource "aws_s3_bucket_public_access_block" "bts" {
  bucket                  = aws_s3_bucket.bts.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "bts" {
  bucket = aws_s3_bucket.bts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bts" {
  bucket = aws_s3_bucket.bts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.bts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
      Resource  = [aws_s3_bucket.bts.arn, "${aws_s3_bucket.bts.arn}/*"],
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.bts]
}

resource "aws_iam_role" "snowflake" {
  name               = "airline-snowflake-bts-read"
  assume_role_policy = local.trust
  lifecycle {
    precondition {
      condition     = (var.snowflake_principal_arn == null) == (var.snowflake_external_id == null)
      error_message = "Set both generated principal/external ID together, or neither (closed trust)."
    }
  }
}

resource "aws_iam_role_policy" "read_prepared" {
  name = "airline-read-prepared-only"
  role = aws_iam_role.snowflake.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow", Action = "s3:GetBucketLocation", Resource = "arn:aws:s3:::${local.bucket}"
      },
      {
        Effect    = "Allow", Action = "s3:ListBucket", Resource = "arn:aws:s3:::${local.bucket}",
        Condition = { StringLike = { "s3:prefix" = ["prepared/", "prepared/*"] } }
      },
      {
        Effect   = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"],
        Resource = "arn:aws:s3:::${local.bucket}/prepared/*"
      }
    ]
  })
}

output "bucket" {
  value = aws_s3_bucket.bts.id
}
output "snowflake_read_role_arn" {
  value = aws_iam_role.snowflake.arn
}

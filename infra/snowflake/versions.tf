terraform {
  required_version = ">= 1.13.4, < 2.0.0"
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "2.21.0"
    }
  }
  backend "s3" {
    bucket              = "airline-state-336805808138-us-east-2"
    key                 = "snowflake/static.tfstate"
    region              = "us-east-2"
    allowed_account_ids = ["336805808138"]
    encrypt             = true
    use_lockfile        = true
  }
}

variable "builder_private_key" {
  description = "Existing protected builder key, supplied only in process memory."
  type        = string
  sensitive   = true
  ephemeral   = true
}

variable "publisher_private_key" {
  description = "Existing protected publisher key; never a state/plan value."
  type        = string
  sensitive   = true
  ephemeral   = true
}

variable "builder_key_passphrase" {
  type      = string
  default   = null
  sensitive = true
  ephemeral = true
}

provider "snowflake" {
  preview_features_enabled = ["snowflake_file_format_resource"]
  organization_name        = "LMOOEWP"
  account_name             = "DQ15927"
  user                     = "AIRLINE_DEV"
  role                     = "AIRLINE_DEV_ROLE"
  authenticator            = "SNOWFLAKE_JWT"
  private_key              = var.builder_private_key
  private_key_passphrase   = var.builder_key_passphrase
  login_timeout            = 15
  client_timeout           = 30
  request_timeout          = 30
  params = {
    query_tag                           = "airline:terraform:static-import"
    statement_timeout_in_seconds        = "60"
    statement_queued_timeout_in_seconds = "10"
    lock_timeout                        = "5"
  }
}

provider "snowflake" {
  alias             = "publisher"
  organization_name = "LMOOEWP"
  account_name      = "DQ15927"
  user              = "AIRLINE_PUBLISHER"
  role              = "AIRLINE_PUBLISHER_ROLE"
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = var.publisher_private_key
  login_timeout     = 15
  client_timeout    = 30
  request_timeout   = 30
  params = {
    query_tag                           = "airline:terraform:static-import-publisher"
    statement_timeout_in_seconds        = "60"
    statement_queued_timeout_in_seconds = "10"
    lock_timeout                        = "5"
  }
}

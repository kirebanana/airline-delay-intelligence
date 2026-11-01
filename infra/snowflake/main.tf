# Existing static objects only. Runtime facts, release schemas, control-table DDL
# and data are owned by the pipeline/migrations, never by this configuration.
variable "snowflake_external_id" {
  description = "Existing integration identifier; preserve the matching AWS trust."
  type        = string
  validation {
    condition     = startswith(var.snowflake_external_id, "DC50202_")
    error_message = "Use the inventoried integration identifier for DC50202 only."
  }
}

resource "snowflake_database" "airline" {
  name         = "AIRLINE_DB"
  comment      = ""
  is_transient = false
  lifecycle { prevent_destroy = true }
}

resource "snowflake_schema" "builder" {
  for_each = {
    RAW         = "Source-shaped BTS ingestion; pipeline owns runtime objects"
    INGEST_TEST = "Isolated fixtures and failed ingestion verification"
  }
  database            = snowflake_database.airline.name
  name                = each.key
  comment             = each.value
  is_transient        = "false"
  with_managed_access = "false"
  lifecycle { prevent_destroy = true }
}

resource "snowflake_schema" "control" {
  provider                    = snowflake.publisher
  database                    = snowflake_database.airline.name
  name                        = "CONTROL"
  comment                     = "Small durable publication control; publisher-owned, not builder-writable"
  data_retention_time_in_days = 1
  is_transient                = "false"
  with_managed_access         = "false"
  lifecycle { prevent_destroy = true }
}

resource "snowflake_account_role" "service" {
  for_each = toset(["AIRLINE_DEV_ROLE", "AIRLINE_PUBLISHER_ROLE", "AIRLINE_READER_ROLE"])
  name     = each.key
  comment  = ""
  lifecycle { prevent_destroy = true }
}

resource "snowflake_warehouse" "development" {
  name                                = "AIRLINE_DEV_WH"
  warehouse_type                      = "STANDARD"
  warehouse_size                      = "XSMALL"
  auto_suspend                        = 60
  auto_resume                         = "true"
  enable_query_acceleration           = "false"
  statement_timeout_in_seconds        = 600
  statement_queued_timeout_in_seconds = 60
  generation                          = "2"
  min_cluster_count                   = 1
  max_cluster_count                   = 1
  scaling_policy                      = "STANDARD"
  query_acceleration_max_scale_factor = 8
  # The existing monitor is ACCOUNT-level, not attached to this warehouse.
  lifecycle { prevent_destroy = true }
}

resource "snowflake_resource_monitor" "budget" {
  name                      = "AIRLINE_BUDGET"
  credit_quota              = 10
  frequency                 = "MONTHLY"
  start_timestamp           = "2026-10-27T06:04:33.346-07:00"
  notify_triggers           = [50]
  suspend_immediate_trigger = 100
  lifecycle { prevent_destroy = true }
}

resource "snowflake_storage_integration_aws" "bts" {
  name                      = "AIRLINE_BTS_S3"
  enabled                   = true
  storage_provider          = "S3"
  storage_allowed_locations = ["s3://airline-bts-336805808138-us-east-2/prepared/"]
  storage_aws_role_arn      = "arn:aws:iam::336805808138:role/airline-snowflake-bts-read"
  storage_aws_external_id   = var.snowflake_external_id
  use_privatelink_endpoint  = "false"
  lifecycle { prevent_destroy = true }
}

resource "snowflake_file_format" "bts" {
  database                       = "AIRLINE_DB"
  schema                         = "RAW"
  name                           = "BTS_CSV_V1"
  format_type                    = "CSV"
  compression                    = "GZIP"
  skip_header                    = 1
  field_optionally_enclosed_by   = "\""
  escape_unenclosed_field        = "NONE"
  empty_field_as_null            = false
  null_if                        = []
  error_on_column_count_mismatch = true
  skip_byte_order_mark           = true
  lifecycle { prevent_destroy = true }
}

resource "snowflake_stage_external_s3" "bts" {
  database            = "AIRLINE_DB"
  schema              = "RAW"
  name                = "BTS_EXTERNAL_STAGE"
  url                 = "s3://airline-bts-336805808138-us-east-2/prepared/"
  storage_integration = snowflake_storage_integration_aws.bts.name
  file_format {
    format_name = snowflake_file_format.bts.fully_qualified_name
  }
  directory {
    enable       = false
    auto_refresh = "false"
  }
  lifecycle {
    prevent_destroy = true
    # This is inherited from the storage integration, where it is managed.
    # The provider forbids configuring it here alongside storage_integration.
    ignore_changes = [use_privatelink_endpoint]
  }
}

# Import blocks are intentional fail-closed boundaries, not create fallbacks.
# The saved plan must contain imports/no-op only, before any state apply.
import {
  to = snowflake_database.airline
  id = "\"AIRLINE_DB\""
}
import {
  for_each = toset(["RAW", "INGEST_TEST"])
  to       = snowflake_schema.builder[each.key]
  id       = "\"AIRLINE_DB\".\"${each.key}\""
}
import {
  to = snowflake_schema.control
  id = "\"AIRLINE_DB\".\"CONTROL\""
}
import {
  for_each = toset(["AIRLINE_DEV_ROLE", "AIRLINE_PUBLISHER_ROLE", "AIRLINE_READER_ROLE"])
  to       = snowflake_account_role.service[each.key]
  id       = "\"${each.key}\""
}
import {
  to = snowflake_warehouse.development
  id = "\"AIRLINE_DEV_WH\""
}
import {
  to = snowflake_resource_monitor.budget
  id = "\"AIRLINE_BUDGET\""
}
import {
  to = snowflake_storage_integration_aws.bts
  id = "\"AIRLINE_BTS_S3\""
}
import {
  to = snowflake_file_format.bts
  id = "AIRLINE_DB|RAW|BTS_CSV_V1"
}
import {
  to = snowflake_stage_external_s3.bts
  id = "\"AIRLINE_DB\".\"RAW\".\"BTS_EXTERNAL_STAGE\""
}

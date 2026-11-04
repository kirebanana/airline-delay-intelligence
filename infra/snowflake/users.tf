# Adoption configuration prepared; no import/apply is authorized until the owner
# authentication preflight and exact three-import/no-change saved-plan approval.
# Never use workload credentials for identity_owner or suppress user TYPE drift.
variable "service_public_keys" {
  description = "Reviewed existing PUBLIC keys, not private authentication material."
  type        = map(string)
}
# snowflake.identity_owner must be a separately approved infrastructure identity,
# not an automatic role upgrade/fallback for any of the workload credentials.
resource "snowflake_service_user" "builder" {
  provider                       = snowflake.identity_owner
  name                           = "AIRLINE_DEV"
  login_name                     = "AIRLINE_DEV"
  display_name                   = "AIRLINE_DEV"
  default_warehouse              = "AIRLINE_DEV_WH"
  default_role                   = "AIRLINE_DEV_ROLE"
  default_secondary_roles_option = "ALL"
  disabled                       = "false"
  rsa_public_key                 = var.service_public_keys["builder"]
  lifecycle {
    prevent_destroy = true
  }
}
resource "snowflake_service_user" "publisher" {
  provider                       = snowflake.identity_owner
  name                           = "AIRLINE_PUBLISHER"
  login_name                     = "AIRLINE_PUBLISHER"
  display_name                   = "AIRLINE_PUBLISHER"
  default_warehouse              = "AIRLINE_DEV_WH"
  default_role                   = "AIRLINE_PUBLISHER_ROLE"
  default_secondary_roles_option = "ALL"
  disabled                       = "false"
  rsa_public_key                 = var.service_public_keys["publisher"]
  lifecycle {
    prevent_destroy = true
  }
}
resource "snowflake_service_user" "reader" {
  provider                       = snowflake.identity_owner
  name                           = "AIRLINE_READER"
  login_name                     = "AIRLINE_READER"
  display_name                   = "AIRLINE_READER"
  default_warehouse              = "AIRLINE_DEV_WH"
  default_role                   = "AIRLINE_READER_ROLE"
  default_secondary_roles_option = "ALL"
  disabled                       = "false"
  rsa_public_key                 = var.service_public_keys["reader"]
  lifecycle {
    prevent_destroy = true
  }
}
import {
  to = snowflake_service_user.builder
  id = "\"AIRLINE_DEV\""
}
import {
  to = snowflake_service_user.publisher
  id = "\"AIRLINE_PUBLISHER\""
}
import {
  to = snowflake_service_user.reader
  id = "\"AIRLINE_READER\""
}

# Human-controlled authentication only. This is NOT a role grant or a fallback for
# the existing workload providers. Keep the profile and its secrets outside Git.
variable "identity_owner_profile" {
  type        = string
  default     = "airline_identity_owner"
  description = "Existing owner-controlled Terraform provider profile, not a CLI connection."
  validation {
    condition     = length(trimspace(var.identity_owner_profile)) > 0 && !contains(["default", "airline"], var.identity_owner_profile)
    error_message = "Use a distinct owner-controlled profile, never the workload/default profile."
  }
}

variable "identity_owner_role" {
  type        = string
  default     = "ACCOUNTADMIN"
  description = "An EXISTING human owner role with visibility on all three users; grants are not managed here."
  validation {
    condition     = !contains(["AIRLINE_DEV_ROLE", "AIRLINE_PUBLISHER_ROLE", "AIRLINE_READER_ROLE", "PUBLIC"], upper(var.identity_owner_role))
    error_message = "A workload role cannot be the user-adoption provider."
  }
}

# Optional native password+MFA, entered only in the owner's local terminal.
# Ephemeral values are excluded from the binary plan and state. SSO/existing
# key-pair profiles leave these null; no personal credential is sent to the agent.
variable "identity_owner_password" {
  type      = string
  default   = null
  sensitive = true
  ephemeral = true
}

variable "identity_owner_passcode" {
  type      = string
  default   = null
  sensitive = true
  ephemeral = true
}

provider "snowflake" {
  alias             = "identity_owner"
  profile           = var.identity_owner_profile
  organization_name = "LMOOEWP"
  account_name      = "DQ15927"
  role              = var.identity_owner_role
  password          = var.identity_owner_password
  passcode          = var.identity_owner_passcode
  login_timeout     = 30
  client_timeout    = 60
  request_timeout   = 60
  params = {
    query_tag                           = "airline:terraform:owner-user-adoption"
    statement_timeout_in_seconds        = "60"
    statement_queued_timeout_in_seconds = "10"
    lock_timeout                        = "5"
  }
}

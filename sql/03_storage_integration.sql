-- Bootstrap completed by the human owner, 2026-10-27. Reference, NOT a rerun script.
-- Agent does not have CREATE INTEGRATION on ACCOUNT. Do not recreate this object.
-- Funding owner-confirmed; Terraform bucket/role deployed in Ohio; exact trust finalized.
-- These are the actual deployed ARN/location: no substitutions are necessary.
-- Use the human owner's existing ACCOUNTADMIN session, never an admin workload role.
-- This binds one exact role/bucket/prefix. Never embed AWS access keys.
CREATE STORAGE INTEGRATION AIRLINE_BTS_S3
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::336805808138:role/airline-snowflake-bts-read'
  STORAGE_ALLOWED_LOCATIONS = ('s3://airline-bts-336805808138-us-east-2/prepared/');

DESC STORAGE INTEGRATION AIRLINE_BTS_S3;
-- Set Terraform's principal/external_id from these actual generated values,
-- review the exact role trust diff, and apply ONLY to the new integration role.
-- Never modify airline-project-dev's permissions or trust.
GRANT USAGE ON INTEGRATION AIRLINE_BTS_S3 TO ROLE AIRLINE_DEV_ROLE;

-- Run as the existing HUMAN account owner in Snowsight. All changes below are
-- session settings only. No GRANT, CREATE, ALTER USER, key rotation or defaults.
USE ROLE ACCOUNTADMIN;
USE SECONDARY ROLES NONE;

SELECT CURRENT_ORGANIZATION_NAME() AS ORGANIZATION,
       CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME,
       CURRENT_ACCOUNT() AS ACCOUNT_LOCATOR,
       CURRENT_REGION() AS REGION,
       CURRENT_USER() AS OWNER_LOGIN,
       CURRENT_ROLE() AS ACTIVE_ROLE;
-- Require LMOOEWP / DQ15927 / DC50202 / AWS_US_EAST_2; OWNER_LOGIN must NOT
-- be AIRLINE_DEV, AIRLINE_PUBLISHER or AIRLINE_READER.

SHOW USERS LIKE 'AIRLINE_DEV';
SELECT "name", "type", "login_name", "display_name", "disabled",
       "default_warehouse", "default_role", "default_secondary_roles"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "name" = 'AIRLINE_DEV';

SHOW USERS LIKE 'AIRLINE_PUBLISHER';
SELECT "name", "type", "login_name", "display_name", "disabled",
       "default_warehouse", "default_role", "default_secondary_roles"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "name" = 'AIRLINE_PUBLISHER';

SHOW USERS LIKE 'AIRLINE_READER';
SELECT "name", "type", "login_name", "display_name", "disabled",
       "default_warehouse", "default_role", "default_secondary_roles"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "name" = 'AIRLINE_READER';
-- Require three exact, unredacted SERVICE users. Preserve observed values, not
-- an assumed default. Stop if the role cannot see them; do not add workload grants.

DESC USER AIRLINE_DEV;
SELECT "property", "value" FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "property" IN ('TYPE', 'RSA_PUBLIC_KEY_FP', 'RSA_PUBLIC_KEY_2_FP');
DESC USER AIRLINE_PUBLISHER;
SELECT "property", "value" FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "property" IN ('TYPE', 'RSA_PUBLIC_KEY_FP', 'RSA_PUBLIC_KEY_2_FP');
DESC USER AIRLINE_READER;
SELECT "property", "value" FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "property" IN ('TYPE', 'RSA_PUBLIC_KEY_FP', 'RSA_PUBLIC_KEY_2_FP');

SHOW PARAMETERS IN USER AIRLINE_DEV;
SHOW PARAMETERS IN USER AIRLINE_PUBLISHER;
SHOW PARAMETERS IN USER AIRLINE_READER;
SHOW GRANTS TO USER AIRLINE_DEV;
SHOW GRANTS TO USER AIRLINE_PUBLISHER;
SHOW GRANTS TO USER AIRLINE_READER;
-- Retain these owner-side for before/after comparison; do not post credentials
-- or an entire personal account export in chat or the public repository.

SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET';
SELECT "name", "level", "credit_quota", "frequency", "suspend_immediately_at"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "name" = 'AIRLINE_BUDGET';
-- Require LEVEL=ACCOUNT and existing quota/triggers unchanged. No ALTER ACCOUNT.

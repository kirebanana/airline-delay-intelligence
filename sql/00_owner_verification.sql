-- Only the human owner runs this with their existing administrative identity.
-- Read-only monitor inspection; no new monitor or account setting changes.
USE ROLE ACCOUNTADMIN;
SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET';

-- Least-privilege visibility needed for automated loader preflight. Grants observation
-- only, not MODIFY or administration. The agent does not execute this grant.
-- GRANT MONITOR ON RESOURCE MONITOR AIRLINE_BUDGET TO ROLE AIRLINE_DEV_ROLE;

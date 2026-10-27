-- Owner-reviewed bootstrap only. AIRLINE_DEV_ROLE cannot execute the monitor or
-- warehouse alterations today. Do not grant ACCOUNTADMIN to the workload user.
-- Select an already authorized human administrative role in Snowsight first.
-- No ALTER ACCOUNT, changes to other warehouses or paid service activation.
CREATE RESOURCE MONITOR IF NOT EXISTS AIRLINE_INGEST_RM
  WITH CREDIT_QUOTA = 5 FREQUENCY = NEVER START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 50 PERCENT DO NOTIFY
           ON 75 PERCENT DO SUSPEND
           ON 90 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE AIRLINE_DEV_WH SET
  ENABLE_QUERY_ACCELERATION = FALSE
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 600
  STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 60
  RESOURCE_MONITOR = AIRLINE_INGEST_RM;

SHOW RESOURCE MONITORS LIKE 'AIRLINE_INGEST_RM';
SHOW WAREHOUSES LIKE 'AIRLINE_DEV_WH';
SHOW PARAMETERS LIKE 'STATEMENT%TIMEOUT_IN_SECONDS' IN WAREHOUSE AIRLINE_DEV_WH;
-- Owner enables their notifications and checks actual trial balance/expiry in
-- Snowsight. Resource monitors exclude storage, transfers and serverless services.

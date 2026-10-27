-- Read-only verification. AIRLINE_BUDGET already protects the ACCOUNT; do not
-- create another monitor, attach it to a warehouse, or alter account-wide settings.
SHOW WAREHOUSES LIKE 'AIRLINE_DEV_WH';
SHOW PARAMETERS LIKE 'STATEMENT%TIMEOUT_IN_SECONDS' IN WAREHOUSE AIRLINE_DEV_WH;
SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET';
-- Expected warehouse: X-Small, auto_suspend=60, acceleration=false,
-- statement timeout=600, queued timeout=60. A null warehouse resource_monitor is
-- normal for account-level protection. Monitor LEVEL must be ACCOUNT; inspect its
-- actual quota, used credits, suspend_at and suspend_immediately_at, not assumed defaults.
-- If invisible as AIRLINE_DEV_ROLE, the owner runs the SHOW as ACCOUNTADMIN.

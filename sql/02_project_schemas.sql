-- Applied successfully using existing AIRLINE_DEV_ROLE, 2026-10-27.
-- These metadata-only namespaces do not start compute or create data tables.
CREATE SCHEMA IF NOT EXISTS AIRLINE_DB.RAW
  COMMENT = 'Source-shaped BTS ingestion; pipeline owns runtime objects';
CREATE SCHEMA IF NOT EXISTS AIRLINE_DB.INGEST_TEST
  COMMENT = 'Isolated fixtures and failed ingestion verification';

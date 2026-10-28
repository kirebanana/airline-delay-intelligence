-- Publisher-owned version 1 migration. Never execute as the builder or an admin.
-- Bootstrap guard is seeded by atomic create-only CTAS, not an unenforced UNIQUE.
CREATE TABLE IF NOT EXISTS AIRLINE_DB.CONTROL.MIGRATION_GUARD AS SELECT 0::NUMBER AS guard;
CREATE TABLE IF NOT EXISTS AIRLINE_DB.CONTROL.TARGETS (
 target VARCHAR, guard NUMBER, fence NUMBER, epoch NUMBER,
 owner VARCHAR, request_id VARCHAR, cancelled BOOLEAN, deadline TIMESTAMP_TZ,
 active VARCHAR, previous VARCHAR
);
CREATE TABLE IF NOT EXISTS AIRLINE_DB.CONTROL.RUNS (
 target VARCHAR, request_id VARCHAR, attempt VARCHAR, fence NUMBER,
 status VARCHAR, release_id VARCHAR
);
CREATE TABLE IF NOT EXISTS AIRLINE_DB.CONTROL.RELEASES (
 target VARCHAR, release_id VARCHAR, attempt VARCHAR, descriptor VARCHAR,
 retired_until TIMESTAMP_TZ
);
CREATE VIEW IF NOT EXISTS AIRLINE_DB.CONTROL.READABLE_RELEASES AS
 SELECT r.target, r.release_id, r.descriptor, r.release_id=t.active AS is_active
 FROM AIRLINE_DB.CONTROL.RELEASES r JOIN AIRLINE_DB.CONTROL.TARGETS t ON r.target=t.target
 WHERE r.release_id=t.active OR r.release_id=t.previous OR r.retired_until>CURRENT_TIMESTAMP();
GRANT SELECT ON VIEW AIRLINE_DB.CONTROL.READABLE_RELEASES TO ROLE AIRLINE_READER_ROLE;

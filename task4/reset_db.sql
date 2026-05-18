-- Drop all indices if you have any to ensure a clean slate for benchmarking before you run any tests

-- reset_db.sql
-- Drops all indices to ensure a clean slate for benchmarking.

DROP INDEX IF EXISTS publ_pubid_idx CASCADE;
DROP INDEX IF EXISTS auth_pubid_idx CASCADE;
DROP INDEX IF EXISTS publ_pubid_unique_idx CASCADE;

-- Note: change the indices names bassed on what you created. 

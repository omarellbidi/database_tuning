-- 1. Physically shuffle the IDs by sorting the table by Year instead
CLUSTER publ USING year_bplus_idx;

-- 2. Drop the old pubID B+ Tree so Postgres doesn't get confused
DROP INDEX pubid_bplus_idx;

-- 3. Create the brand new Hash Index for pubID
CREATE INDEX pubid_hash_idx ON publ USING HASH (pubid);

-- 4. Tell the database to update its brain
ANALYZE publ;



-- 1. Drop the B+ Tree so Postgres doesn't use it
DROP INDEX IF EXISTS title_bplus_idx;

-- 2. Create the Hash Index
CREATE INDEX title_hash_idx ON publ USING HASH (booktitle);

-- 3. Update the brain
ANALYZE publ;

-- 4. Get the Query Plan (Take a screenshot!)
EXPLAIN SELECT * FROM Publ WHERE booktitle = 'SBRN';




-- 1. Create a temporary B+ Tree just to shuffle the data
CREATE INDEX temp_shuffle_idx ON publ (pubid);

-- 2. Shuffle the data by pubID (This guarantees Year is NO LONGER physically ordered!)
CLUSTER publ USING temp_shuffle_idx;

-- 3. Drop the old Year B+ Tree
DROP INDEX IF EXISTS year_bplus_idx;

-- 4. Create the Hash Index for Year
CREATE INDEX year_hash_idx ON publ USING HASH (year);

-- 5. Update the brain
ANALYZE publ;

-- 6. Get the Query Plan (Take a screenshot!)
EXPLAIN SELECT * FROM Publ WHERE year = '1974';
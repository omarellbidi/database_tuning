-- ==========================================
-- CLUSTERED B+ TREE SETUP & EXECUTION
-- ==========================================

-- --- STEP 0: CREATE THE INDEXES (If not already done) ---
-- CREATE INDEX year_bplus_idx ON publ (year);
-- CREATE INDEX title_bplus_idx ON publ (booktitle);
-- CREATE INDEX pubid_bplus_idx ON publ (pubid);


-- --- STEP 1: TEST PREP FOR HIGH SELECTIVITY (Year) ---
-- Physically sort by Year
CLUSTER publ USING year_bplus_idx;
-- Update database statistics
ANALYZE publ;
-- (Run Python High Selectivity Test Here)


-- --- STEP 2: TEST PREP FOR LOW SELECTIVITY (Booktitle) ---
-- Physically re-sort by Title
CLUSTER publ USING title_bplus_idx;
-- Update database statistics
ANALYZE publ;
-- (Run Python Low Selectivity Test Here)


-- --- STEP 3: TEST PREP FOR POINT & IN PREDICATE (pubID) ---
-- Physically re-sort by pubID
CLUSTER publ USING pubid_bplus_idx;
-- Update database statistics
ANALYZE publ;
-- (Run Python Point & IN Predicate Tests Here)
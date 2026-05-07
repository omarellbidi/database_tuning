- Create the three Non-Clustered B+ Tree indexes
CREATE INDEX year_bplus_idx ON publ (year);
CREATE INDEX title_bplus_idx ON publ (booktitle);
CREATE INDEX pubid_bplus_idx ON publ (pubid);

-- tests Point, IN, and High Selectivity 
-- . Physically sort by Title (This scatters Year and pubID)
CLUSTER publ USING title_bplus_idx;

-- . Update the database statistics
ANALYZE publ;

-- Tests Low Selectivity
-- 1. Physically sort by Year (This scatters the Booktitle data)
CLUSTER publ USING year_bplus_idx;

-- 2. Update the database statistics
ANALYZE publ;


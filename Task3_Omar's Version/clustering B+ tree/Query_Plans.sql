

-- 1. High Selectivity (Year)
EXPLAIN SELECT * FROM Publ WHERE year = '1974';

-- 2. Low Selectivity (Booktitle)
EXPLAIN SELECT * FROM Publ WHERE booktitle = 'SBRN';

-- 3. Point Query (Single pubID)
EXPLAIN SELECT * FROM Publ WHERE pubID = 'journals/automatica/DehghaniLA';

-- 4. IN Predicate (Multiple pubIDs)
EXPLAIN SELECT * FROM Publ WHERE pubID IN ('journals/automatica/DehghaniLA', 'conf/crypto/BressonSS02', 'conf/isbi/ArdekaniS04');
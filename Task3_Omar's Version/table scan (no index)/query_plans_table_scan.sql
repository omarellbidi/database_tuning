-- 1. Point Query (pubID)
EXPLAIN SELECT * FROM Publ WHERE pubID = 'conf/sigmod/LiuC07';

-- 2. Multipoint Low Selectivity (booktitle)
EXPLAIN SELECT * FROM Publ WHERE booktitle = 'SBRN';

-- 3. Multipoint IN Predicate (3 pubIDs)
EXPLAIN SELECT * FROM Publ WHERE pubID IN ('conf/sigmod/LiuC07', 'conf/cp/SimonisO08', 'journals/jal/Xu00');

-- 4. Multipoint High Selectivity (year)
EXPLAIN SELECT * FROM Publ WHERE year = '1974';
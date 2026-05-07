-- Used for Point Query and IN Predicate baseline
SELECT pubID FROM publ ORDER BY RANDOM() LIMIT 10;

-- Used for Low Selectivity (booktitle) baseline
SELECT booktitle 
FROM (SELECT DISTINCT booktitle FROM publ WHERE booktitle IS NOT NULL) as sub 
ORDER BY RANDOM() 
LIMIT 10;

-- Used for High Selectivity (year) baseline
SELECT year 
FROM (SELECT DISTINCT year FROM publ) AS sub 
ORDER BY RANDOM() 
LIMIT 10;
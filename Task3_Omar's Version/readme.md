# Database Index Tuning Benchmark: Execution Guide

This guide explains the exact order of operations required to reproduce our database benchmark tests.

**CRITICAL RULE:** Because PostgreSQL is stateful, the physical ordering of the data on the hard drive matters. You **MUST** run these tests in this exact order, and execute the SQL prep blocks *before* running each phase.

---

## Phase 1: Baseline (Table Scan / No Indexes)

*Ensure your table has no indexes on `pubid`, `booktitle`, or `year` before starting this phase.*

**1. Gather Sample Data (SQL)**

Run these queries to fetch random existing data. Plug these results into the `SAMPLE_PUBIDS`, `SAMPLE_TITLES`, and `SAMPLE_YEARS` arrays in your Python script.

```sql
-- Point Query and IN Predicate baseline
SELECT pubID FROM publ ORDER BY RANDOM() LIMIT 10;

-- Low Selectivity (booktitle) baseline
SELECT booktitle FROM (SELECT DISTINCT booktitle FROM publ WHERE booktitle IS NOT NULL) as sub ORDER BY RANDOM() LIMIT 10;

-- High Selectivity (year) baseline
SELECT year FROM (SELECT DISTINCT year FROM publ) AS sub ORDER BY RANDOM() LIMIT 10;
```

**2. Run Python Tests**

Uncomment and run all 4 tests in the Python script one by one.

- `run_throughput_test("POINT")`
- `run_throughput_test("IN_PREDICATE")`
- `run_throughput_test("LOW_SELECTIVITY")`
- `run_throughput_test("HIGH_SELECTIVITY")`

---

## Phase 2: Non-Clustered B+ Tree

*Goal: Test indexes while guaranteeing the physical data on the disk is completely scattered.*

**1. Create the Indexes (SQL)**

```sql
CREATE INDEX year_bplus_idx ON publ (year);
CREATE INDEX title_bplus_idx ON publ (booktitle);
CREATE INDEX pubid_bplus_idx ON publ (pubid);
```

**2. Prepare & Run: Point, IN, and High Selectivity**

Run this SQL to physically sort the table by Title. This guarantees that `year` and `pubid` are scattered, forcing a true non-clustered lookup.

```sql
CLUSTER publ USING title_bplus_idx;
ANALYZE publ;
```

- **Run Python:** `POINT`, `IN_PREDICATE`, and `HIGH_SELECTIVITY`.

**3. Prepare & Run: Low Selectivity**

Run this SQL to physically sort the table by Year. This scatters the `booktitle` data.

```sql
CLUSTER publ USING year_bplus_idx;
ANALYZE publ;
```

- **Run Python:** `LOW_SELECTIVITY`.

---

## Phase 3: Clustered B+ Tree

*Goal: Test indexes where the physical data on the disk perfectly matches the index order.*

**1. Prepare & Run: High Selectivity (Year)**

```sql
CLUSTER publ USING year_bplus_idx;
ANALYZE publ;
```

- **Run Python:** `HIGH_SELECTIVITY`.

**2. Prepare & Run: Low Selectivity (Booktitle)**

```sql
CLUSTER publ USING title_bplus_idx;
ANALYZE publ;
```

- **Run Python:** `LOW_SELECTIVITY`.

**3. Prepare & Run: Point & IN Predicate (pubID)**

```sql
CLUSTER publ USING pubid_bplus_idx;
ANALYZE publ;
```

- **Run Python:** `POINT` and `IN_PREDICATE`.

---

## Phase 4: Hash Indexes

*Goal: Replace B+ Trees with Hash indexes, ensuring data remains physically un-clustered for the test.*

**1. Prepare & Run: Point & IN Predicate (pubID)**

```sql
-- Shuffle data by Year, drop the old B+ tree, create Hash
CLUSTER publ USING year_bplus_idx;
DROP INDEX pubid_bplus_idx;
CREATE INDEX pubid_hash_idx ON publ USING HASH (pubid);
ANALYZE publ;
```

- **Run Python:** `POINT` and `IN_PREDICATE`.

**2. Prepare & Run: Low Selectivity (Booktitle)**

```sql
-- Data is already shuffled by Year from the previous step
DROP INDEX IF EXISTS title_bplus_idx;
CREATE INDEX title_hash_idx ON publ USING HASH (booktitle);
ANALYZE publ;
```

- **Run Python:** `LOW_SELECTIVITY`.

**3. Prepare & Run: High Selectivity (Year)**

```sql
-- Create a temporary B+ Tree to shuffle data by pubID so Year is scattered
CREATE INDEX temp_shuffle_idx ON publ (pubid);
CLUSTER publ USING temp_shuffle_idx;

-- Drop old B+ tree and create Hash
DROP INDEX IF EXISTS year_bplus_idx;
CREATE INDEX year_hash_idx ON publ USING HASH (year);
ANALYZE publ;
```

- **Run Python:** `HIGH_SELECTIVITY`.

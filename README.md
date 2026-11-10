# Database Tuning

Group B15's assignments for the Database Tuning proseminar at the University of Salzburg (summer semester 2026).
Group members: Omar El Lbidi, Mitsuhiro Kitajima and Nargiz Sadykova.

All experiments run on PostgreSQL, some also on MariaDB, with Python scripts using psycopg2 and pymysql.
The data comes from the DBLP publication dataset (tables `Auth` and `Publ`).
Every assignment has a LaTeX report with the results.

## Assignments

### 1. Bulk loading (root folder, report in `Task 1/`)

Loading the `Auth` table from a TSV file, row by row and with the bulk loading tools of each database.

| Approach | Runtime |
|---|---|
| Row-by-row INSERT, PostgreSQL | 101.80 s |
| Row-by-row INSERT, MariaDB | 129.09 s |
| `COPY`, PostgreSQL | 4.10 s |
| `LOAD DATA LOCAL INFILE`, MariaDB | 4.12 s |

Scripts: `auth.py`, `auth_efficient.py`, `auth_mariadb.py`, `auth_mariadb_efficient.py`

### 2. Query tuning (`task2/`)

Rewriting queries (for example correlated subqueries into joins) and comparing the query plans and runtimes with `EXPLAIN ANALYZE` on PostgreSQL and MariaDB.
`populate.py` generates the test data.

### 3. Index tuning (`Task3_Omar's Version/`, `task3/`)

Throughput of point queries, multipoint queries on `booktitle` and `year`, and IN queries on `Publ` with no index, a clustering B+ tree, a non-clustering B+ tree and a hash index.
`benchmark.py` runs each query type for 65 seconds with random parameters and randomizes the physical order of the table before the tests that need it.
`Task3_Omar's Version/` is the version used in the report, `task3/` is a second implementation.

### 4. Join tuning (`task4/`)

`benchmark.py` runs two joins between `Auth` and `Publ` with different indexes and forces hash join, sort-merge join and indexed nested loop join through the planner settings (`enable_hashjoin`, `enable_mergejoin`, `enable_nestloop`).

### 5. Concurrency tuning (`task5/`)

Concurrent bank transfers with a thread pool, comparing throughput, correctness and rollbacks under Read Committed and Serializable for two ways of writing the transaction.

## Running the scripts

The scripts expect a local PostgreSQL or MariaDB server with the DBLP tables loaded.
Connection settings are in `conf.ini`, `conf.py` or `db_config.py` in each folder, and the TSV file paths in the Task 1 scripts point to a local folder, so they need to be adjusted.

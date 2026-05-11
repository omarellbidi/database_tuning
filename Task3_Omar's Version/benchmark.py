import time
import random
import argparse
import psycopg2
from db_config import get_connection 

# ==========================================
# 1. DYNAMIC SAMPLE DATA CACHE
# ==========================================
# We initialize empty lists here; they will be filled by the database
SAMPLE_PUBIDS = []
SAMPLE_TITLES = []
SAMPLE_YEARS = []

def pre_fetch_sample_data(conn):
    """Fetches a large pool of random data BEFORE the tests start to defeat RAM caching."""
    print("Pre-fetching dynamic random sample data from the database...")
    cur = conn.cursor()
    
    # 1. Get 1,000 random pubIDs 
    cur.execute("SELECT pubid FROM publ WHERE pubid IS NOT NULL ORDER BY RANDOM() LIMIT 1000;")
    global SAMPLE_PUBIDS
    SAMPLE_PUBIDS = [row[0] for row in cur.fetchall()]
    
    # 2. Get 100 random titles 
    cur.execute("SELECT booktitle FROM (SELECT DISTINCT booktitle FROM publ WHERE booktitle IS NOT NULL) AS sub ORDER BY RANDOM() LIMIT 100;")
    global SAMPLE_TITLES
    SAMPLE_TITLES = [row[0] for row in cur.fetchall()]
    
    # 3. Get 50 random years 
    cur.execute("SELECT year FROM (SELECT DISTINCT year FROM publ WHERE year IS NOT NULL) AS sub ORDER BY RANDOM() LIMIT 50;")
    global SAMPLE_YEARS
    SAMPLE_YEARS = [row[0] for row in cur.fetchall()]
    
    cur.close()
    print(f"Loaded {len(SAMPLE_PUBIDS)} IDs, {len(SAMPLE_TITLES)} Titles, and {len(SAMPLE_YEARS)} Years.\n")

# ==========================================
# 2. EXECUTION ENGINE
# ==========================================
def run_65s_benchmark(conn, test_name, query_template, param_generator):
    cur = conn.cursor()
    
    # 1. Get the Query Plan ONCE
    cur.execute("EXPLAIN ANALYZE " + query_template, param_generator())
    plan = "\n".join(row[0] for row in cur.fetchall())
    print(f"\n--- {test_name} ---")
    print("QUERY PLAN:")
    print(plan)
    print("Running 65-second stress test...")

    # 2. The 65-Second Stress Test Loop
    query_count = 0
    start_time = time.time()
    
    while time.time() - start_time < 65:
        params = param_generator() 
        cur.execute(query_template, params)
        cur.fetchall() 
        query_count += 1

    # 3. Calculate Results
    duration = time.time() - start_time
    avg_runtime = duration / query_count
    qps = query_count / duration

    result_str = (
        f"DONE. Total Queries: {query_count}\n"
        f"Average Runtime: {avg_runtime:.6f} seconds\n"
        f"Throughput: {qps:.2f} queries/second\n"
    )
    
    print(result_str)
    
    # Append results to a text file s
    with open("benchmark_results.txt", "a") as f:
        f.write(f"--- {test_name} ---\n")
        f.write(result_str + "\n")
    
    cur.close()

def execute_sql(conn, sql_script):
    """Helper to run setup/teardown SQL blocks cleanly"""
    # close any lingering transactions from the previous benchmark loop
    conn.commit() 
    
    old_autocommit = conn.autocommit
    conn.autocommit = True
    
    cur = conn.cursor()
    cur.execute(sql_script)
    cur.close()
    
    conn.autocommit = old_autocommit

# ==========================================
# 3. QUERY & PARAMETER GENERATORS
# ==========================================
queries = {
    "POINT": (
        "SELECT * FROM publ WHERE pubID = %s", 
        lambda: (random.choice(SAMPLE_PUBIDS),)
    ),
    "LOW_SELECTIVITY": (
        "SELECT * FROM publ WHERE booktitle = %s", 
        lambda: (random.choice(SAMPLE_TITLES),)
    ),
    "IN_PREDICATE": (
        "SELECT * FROM publ WHERE pubID IN (%s, %s, %s)", 
        lambda: tuple(random.sample(SAMPLE_PUBIDS, 3))
    ),
    "HIGH_SELECTIVITY": (
        "SELECT * FROM publ WHERE year = %s", 
        lambda: (random.choice(SAMPLE_YEARS),)
    )
}

# ==========================================
# 4. MAIN ORCHESTRATOR WITH ARGUMENT PARSING
# ==========================================
def main():
    # Set up the command-line arguments
    parser = argparse.ArgumentParser(description="Run specific database index benchmarks.")
    parser.add_argument(
        '--test', 
        type=str, 
        choices=['all', 'scan', 'clustered', 'nonclustered', 'hash'], 
        default='all', 
        help="Choose which index type to test: 'scan', 'clustered', 'nonclustered', 'hash', or 'all'"
    )
    args = parser.parse_args()

    conn = get_connection()
    
    # ---------------------------------------------------------
    # DYNAMIC DATA PRE-FETCH
    # ---------------------------------------------------------
    pre_fetch_sample_data(conn)
    
    print(f"STARTING DATABASE TUNING BENCHMARKS...")
    print(f"Selected Mode: [{args.test.upper()}]")
    print("NOTE: Ensure this script is running directly on the database server to eliminate network latency!\n")
    
    # Clear out the log file before a fresh run
    with open("benchmark_results.txt", "a") as f:
        f.write(f"\n================ NEW BENCHMARK RUN: {args.test.upper()} ================\n")

# ---------------------------------------------------------
# PHASE 1: TABLE SCAN (No Indexes)
# ---------------------------------------------------------
    if args.test in ['all', 'scan']:
        print("================ PHASE 1: TABLE SCAN ================")
        execute_sql(conn, """
            -- 1. Drop all possible indexes from any previous tests
            DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;
            
            -- 2. Create a random column, sort the physical disk by it, and delete it.
            -- This guarantees the table is physically randomized for the baseline test!
            ALTER TABLE publ ADD COLUMN IF NOT EXISTS temp_rand float DEFAULT random();
            CREATE INDEX temp_rand_idx ON publ(temp_rand);
            CLUSTER publ USING temp_rand_idx;
            ALTER TABLE publ DROP COLUMN temp_rand;
            
            -- 3. Update the database 
            ANALYZE publ;
        """)
        for shape, (sql, param_gen) in queries.items():
            run_65s_benchmark(conn, f"Table Scan - {shape}", sql, param_gen)

    # ---------------------------------------------------------
    # PHASE 2: CLUSTERED B+ TREE
    # ---------------------------------------------------------
    if args.test in ['all', 'clustered']:
        print("================ PHASE 2: CLUSTERED B+ TREE ================")
        config_clustered = {
            "POINT":            ("pubID", "CREATE INDEX pubid_idx ON publ(pubID); CLUSTER publ USING pubid_idx;"),
            "IN_PREDICATE":     ("pubID", "CREATE INDEX pubid_idx ON publ(pubID); CLUSTER publ USING pubid_idx;"),
            "LOW_SELECTIVITY":  ("booktitle", "CREATE INDEX title_idx ON publ(booktitle); CLUSTER publ USING title_idx;"),
            "HIGH_SELECTIVITY": ("year", "CREATE INDEX year_idx ON publ(year); CLUSTER publ USING year_idx;")
        }
        
        for shape, (col, setup_sql) in config_clustered.items():
            execute_sql(conn, "DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;")
            execute_sql(conn, setup_sql + " ANALYZE publ;")
            run_65s_benchmark(conn, f"Clustered B-Tree - {shape}", queries[shape][0], queries[shape][1])

    # ---------------------------------------------------------
    # PHASE 3: NON-CLUSTERED B+ TREE
    # ---------------------------------------------------------
    if args.test in ['all', 'nonclustered']:
        print("================ PHASE 3: NON-CLUSTERED B+ TREE ================")
        config_non_clustered = {
            "POINT":            ("pubID", "CREATE INDEX pubid_idx ON publ(pubID); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "IN_PREDICATE":     ("pubID", "CREATE INDEX pubid_idx ON publ(pubID); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "LOW_SELECTIVITY":  ("booktitle", "CREATE INDEX title_idx ON publ(booktitle); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "HIGH_SELECTIVITY": ("year", "CREATE INDEX year_idx ON publ(year); CREATE INDEX temp_idx ON publ(booktitle); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;")
        }

        for shape, (col, setup_sql) in config_non_clustered.items():
            execute_sql(conn, "DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;")
            execute_sql(conn, setup_sql + " ANALYZE publ;")
            run_65s_benchmark(conn, f"Non-Clustered B-Tree - {shape}", queries[shape][0], queries[shape][1])

    # ---------------------------------------------------------
    # PHASE 4: HASH INDEX
    # ---------------------------------------------------------
    if args.test in ['all', 'hash']:
        print("================ PHASE 4: HASH INDEX ================")
        config_hash = {
            "POINT":            ("pubID", "CREATE INDEX pubid_idx ON publ USING HASH(pubID); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "IN_PREDICATE":     ("pubID", "CREATE INDEX pubid_idx ON publ USING HASH(pubID); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "LOW_SELECTIVITY":  ("booktitle", "CREATE INDEX title_idx ON publ USING HASH(booktitle); CREATE INDEX temp_idx ON publ(year); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;"),
            "HIGH_SELECTIVITY": ("year", "CREATE INDEX year_idx ON publ USING HASH(year); CREATE INDEX temp_idx ON publ(booktitle); CLUSTER publ USING temp_idx; DROP INDEX temp_idx;")
        }

        for shape, (col, setup_sql) in config_hash.items():
            execute_sql(conn, "DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;")
            execute_sql(conn, setup_sql + " ANALYZE publ;")
            run_65s_benchmark(conn, f"Hash Index - {shape}", queries[shape][0], queries[shape][1])

    # ---------------------------------------------------------
    # FINAL CLEANUP 
    # ---------------------------------------------------------
    print("================ CLEANING UP ================")
    execute_sql(conn, """
        DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;
        ALTER TABLE publ SET WITHOUT CLUSTER;
        ANALYZE publ;
    """)
    
    conn.close()
    print("ALL REQUESTED BENCHMARKS COMPLETED SUCCESSFULLY.")
    print("Results have been saved to 'benchmark_results.txt'")

if __name__ == "__main__":
    main()
    

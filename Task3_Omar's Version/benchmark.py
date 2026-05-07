import time
import random
import argparse
import psycopg2
from db_config import get_connection 

# ==========================================
# 1. SAMPLE DATA (Randomly picked for cache busting)
# ==========================================
SAMPLE_PUBIDS = [
    'journals/automatica/DehghaniLA', 'conf/crypto/BressonSS02', 'conf/isbi/ArdekaniS04',
    'conf/dac/Lanzo92', 'conf/ipps/Sobe04', 'conf/conpar/LeiteB92',
    'journals/tomccap/GhineaDGC07', 'conf/cp/SimonisO08', 'journals/jal/Xu00', 'conf/sigmod/LiuC07'
]

SAMPLE_TITLES = [
    'SBRN', 'WRAC', 'IJCSLP Workshop on Concurrent and Parallel Implementati...',
    'ICVS', 'RelMiCS', 'Security and Management', 'RSKD',
    'Computer Science Today', 'Architecture and Protocols for High-Speed Networks',
    'Computational Discovery of Scientific Knowledge'
]

SAMPLE_YEARS = ['1974', '1952', '1994', '1959', '2005', '1976', '1950', '1991', '1968', '1987']

# ==========================================
# 2. CORE EXECUTION ENGINE
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

    print(f"DONE. Total Queries: {query_count}")
    print(f"Average Runtime: {avg_runtime:.6f} seconds")
    print(f"Throughput: {qps:.2f} queries/second\n")
    
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
    
    print(f"STARTING DATABASE TUNING BENCHMARKS...")
    print(f"Selected Mode: [{args.test.upper()}]")
    print("NOTE: Ensure this script is running directly on the database server to eliminate network latency!\n")

    # ---------------------------------------------------------
    # PHASE 1: TABLE SCAN (No Indexes)
    # ---------------------------------------------------------
    if args.test in ['all', 'scan']:
        print("================ PHASE 1: TABLE SCAN ================")
        execute_sql(conn, """
            DROP INDEX IF EXISTS year_idx, title_idx, pubid_idx;
            ALTER TABLE publ SET WITHOUT CLUSTER;
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

if __name__ == "__main__":
    main()

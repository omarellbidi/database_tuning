import psycopg2
from db_config import get_connection

# The two queries to test
QUERIES = {
    "Q1_Big_Join": """
        SELECT name, title 
        FROM Auth, Publ 
        WHERE Auth.pubID=Publ.pubID;
    """,
    "Q2_Selective_Join": """
        SELECT title 
        FROM Auth, Publ 
        WHERE Auth.pubID=Publ.pubID AND Auth.name='Divesh Srivastava';
    """
}

def execute_sql(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

def drop_all_indexes(conn):
    # Standardized cleanup function for the group using matching names
    sql = """
    DROP INDEX IF EXISTS publ_pubid_idx CASCADE;
    DROP INDEX IF EXISTS auth_pubid_idx CASCADE;
    DROP INDEX IF EXISTS publ_pubid_unique_idx CASCADE;
    """
    execute_sql(conn, sql)

def set_join_switches(conn, nestloop='on', mergejoin='on', hashjoin='on'):
    execute_sql(conn, f"SET enable_nestloop TO {nestloop};")
    execute_sql(conn, f"SET enable_mergejoin TO {mergejoin};")
    execute_sql(conn, f"SET enable_hashjoin TO {hashjoin};")

def run_explain_analyze(conn, test_name, query_name, sql, file):
    print(f"Running: {test_name} - {query_name}...")
    file.write(f"\n{'='*50}\n")
    file.write(f"TEST: {test_name} | QUERY: {query_name}\n")
    file.write(f"{'='*50}\n")
    
    try:
        with conn.cursor() as cur:
            cur.execute("EXPLAIN ANALYZE " + sql)
            plan = cur.fetchall()
            for row in plan:
                file.write(row[0] + "\n")
    except psycopg2.errors.QueryCanceled:
        file.write("QUERY CANCELLED: Exceeded 10-minute timeout limit.\n")
        conn.rollback() 
    except Exception as e:
        file.write(f"ERROR: {e}\n")
        conn.rollback()

def main():
    print("Connecting to database using db_config.py...")
    conn = get_connection()
    
    execute_sql(conn, "SET statement_timeout = '600000';") 

    with open("assignment4_results.txt", "w") as f:
        
        # ==========================================
        # TASK 1: System Proposals (All joins enabled)
        # ==========================================
        f.write("\n\n>>> TASK 1: SYSTEM PROPOSALS\n")
        # 1a: No index
        drop_all_indexes(conn)
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "1a: No Index", q_name, sql, f)

        # 1b: Unique non-clustering index on Publ.pubID
        drop_all_indexes(conn)
        execute_sql(conn, "CREATE UNIQUE INDEX publ_pubid_unique_idx ON Publ(pubID); ANALYZE Publ;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "1b: Unique Non-Clustering on Publ.pubID", q_name, sql, f)

        # 1c: Clustering on Publ.pubID and Auth.pubID
        drop_all_indexes(conn)
        execute_sql(conn, "CREATE INDEX publ_pubid_idx ON Publ(pubID);")
        execute_sql(conn, "CREATE INDEX auth_pubid_idx ON Auth(pubID);")
        execute_sql(conn, "CLUSTER Publ USING publ_pubid_idx; CLUSTER Auth USING auth_pubid_idx; ANALYZE Publ; ANALYZE Auth;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "1c: Clustering on Publ.pubID and Auth.pubID", q_name, sql, f)

        drop_all_indexes(conn) # Clean up

        # ==========================================
        # TASK 2: Forced Indexed Nested Loop Join 
        # ==========================================
        f.write("\n\n>>> TASK 2: FORCED INDEXED NESTED LOOP JOIN\n")
        set_join_switches(conn, nestloop='on', mergejoin='off', hashjoin='off')

        # 2a: Non-clustering on Publ.pubID
        drop_all_indexes(conn)
        execute_sql(conn, "CREATE INDEX publ_pubid_idx ON Publ(pubID); ANALYZE Publ;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "2a: INLJ - Non-Clustered Publ", q_name, sql, f)

        # 2b: Non-clustering on Auth.pubID
        drop_all_indexes(conn)
        execute_sql(conn, "CREATE INDEX auth_pubid_idx ON Auth(pubID); ANALYZE Auth;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "2b: INLJ - Non-Clustered Auth", q_name, sql, f)

        # 2c: Non-clustering on both
        drop_all_indexes(conn)
        execute_sql(conn, "CREATE INDEX publ_pubid_idx ON Publ(pubID); ANALYZE Publ;")
        execute_sql(conn, "CREATE INDEX auth_pubid_idx ON Auth(pubID); ANALYZE Auth;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "2c: INLJ - Non-Clustered Both", q_name, sql, f)

        # ==========================================
        # TASK 3: Forced Sort-Merge Join (Omar's Part)
        # ==========================================
        f.write("\n\n>>> TASK 3: FORCED SORT-MERGE JOIN\n")
        set_join_switches(conn, nestloop='off', mergejoin='on', hashjoin='off')

        # 3a: Without index
        drop_all_indexes(conn)
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3a: SMJ - No Index", q_name, sql, f)

        # 3b: Two non-clustering indexes
        execute_sql(conn, "CREATE INDEX publ_pubid_idx ON Publ(pubID); ANALYZE Publ;")
        execute_sql(conn, "CREATE INDEX auth_pubid_idx ON Auth(pubID); ANALYZE Auth;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3b: SMJ - Two Non-Clustered", q_name, sql, f)

        # 3c: Two clustering indexes
        execute_sql(conn, "CLUSTER Publ USING publ_pubid_idx; CLUSTER Auth USING auth_pubid_idx;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3c: SMJ - Two Clustered", q_name, sql, f)

        # ==========================================
        # TASK 4: Forced Hash Join 
        # ==========================================
        f.write("\n\n>>> TASK 4: FORCED HASH JOIN\n")
        set_join_switches(conn, nestloop='off', mergejoin='off', hashjoin='on')

        # 4a: No index
        drop_all_indexes(conn)
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "4a: HJ - No Index", q_name, sql, f)

  
    # Reset table and runtime configs
    drop_all_indexes(conn) 
    set_join_switches(conn) # Reset to all on
    execute_sql(conn, "SET statement_timeout = '0';") 
    conn.close()
    print("\nBenchmarking complete. All 4 Tasks are fully merged and safe to run!")

if __name__ == "__main__":
    main()

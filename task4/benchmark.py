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
    # Influences the optimizer's choices by toggling algorithm switches [cite: 61]
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
            # Executes the query and records the plan details 
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
    
    # Enforce the 10-minute timeout limit rule for the assignment [cite: 32]
    execute_sql(conn, "SET statement_timeout = '600000';") 

    with open("assignment4_results.txt", "w") as f:
        
        # ==========================================
        # TASK 1: System Proposals (All joins enabled)
        # ==========================================
        # TODO: Implement Task 1 here.
        pass

        # ==========================================
        # TASK 2: Forced Indexed Nested Loop Join
        # ==========================================
        # TODO: Implement Task 2 here. 
        pass

        # ==========================================
        # TASK 3: Forced Sort-Merge Join
        # ==========================================
        f.write("\n\n>>> TASK 3: FORCED SORT-MERGE JOIN\n")
        set_join_switches(conn, nestloop='off', mergejoin='on', hashjoin='off')

        # 3a: Without index [cite: 47]
        drop_all_indexes(conn)
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3a: SMJ - No Index", q_name, sql, f)

        # 3b: Two non-clustering indexes [cite: 48]
        execute_sql(conn, "CREATE INDEX publ_pubid_idx ON Publ(pubID); ANALYZE Publ;")
        execute_sql(conn, "CREATE INDEX auth_pubid_idx ON Auth(pubID); ANALYZE Auth;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3b: SMJ - Two Non-Clustered", q_name, sql, f)

        # 3c: Two clustering indexes [cite: 49]
        execute_sql(conn, "CLUSTER Publ USING publ_pubid_idx; CLUSTER Auth USING auth_pubid_idx;")
        for q_name, sql in QUERIES.items():
            run_explain_analyze(conn, "3c: SMJ - Two Clustered", q_name, sql, f)

        # ==========================================
        # TASK 4: Forced Hash Join
        # ==========================================
        # TODO: Implement Task 4 here.
        pass

    # Reset timeout and close connection
    execute_sql(conn, "SET statement_timeout = '0';") 
    conn.close()
    print("\nBenchmarking complete.")

if __name__ == "__main__":
    main()

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

def run_explain_analyze(conn, test_name, query_name, sql, file):
    # TODO: Implement the EXPLAIN ANALYZE execution here
    pass

def main():
    print("Connecting to database using db_config.py...")
    conn = get_connection()
    
    # Enforce the 10-minute timeout limit rule for the assignment
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
       
        pass

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

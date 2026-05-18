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
        # TODO: Implement Task 3 here.
       
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

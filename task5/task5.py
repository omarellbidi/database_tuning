import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE, ISOLATION_LEVEL_REPEATABLE_READ, ISOLATION_LEVEL_READ_UNCOMMITTED
from conf import get_connection

from concurrent.futures import ThreadPoolExecutor, wait
import time
import random

QUERIES = {
    "query_a": """
                DO $$
                DECLARE e INT;
                BEGIN
                SELECT balance INTO e FROM Accounts WHERE account = %(i)s;
                UPDATE Accounts SET balance = e + 1 WHERE account = %(i)s;
                END $$;

                DO $$
                DECLARE c INT;
                BEGIN
                    SELECT balance INTO c FROM Accounts WHERE account = 0;
                    UPDATE Accounts SET balance = c - 1 WHERE account = 0;
                END $$;
                """,

    "query_b": """UPDATE Accounts SET balance=balance+1 WHERE account=%(i)s; 
                UPDATE Accounts SET balance=balance-1 WHERE account=0;"""
}

## Database operations
def connect() -> psycopg2.extensions.connection:
    conn = get_connection()
    return conn

def disconnect(conn: psycopg2.extensions.connection) -> None:
    conn.close()

## Table Creation
def create_table(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS accounts;")
        cur.execute("""
        CREATE TABLE accounts 
        (
        account INT,
        balance INT
        );

        INSERT INTO accounts (account, balance)
        SELECT account, balance
        FROM (
            SELECT 0 AS account, 100 AS balance
            UNION ALL
            SELECT i, 0
            FROM generate_series(1, 100) AS i
        ) t;
        """)
    conn.commit()

### Transaction operators 
def transaction(query: str, i: int, isolation_level: int) -> None:
    while True:
        try:
            conn = get_connection()
            # Set isolation level correctly for the connection session
            conn.set_session(isolation_level=isolation_level, autocommit=False)
            with conn.cursor() as cur:
                # Execute the query string directly
                cur.execute(query, {"i": i})
            conn.commit()
            conn.close()
            break
        except Exception as e:
            conn.rollback()
            conn.close()
            # Retry on serialization failure or deadlock
            time.sleep(random.uniform(0.001, 0.01))
            continue

def run_transactions(num_threads: int, max_concurrent: int, query: str, isolation_level: int) -> float:
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            # account numbers are 1 to 100, corresponding to employee accounts
            executor.submit(transaction, query, i, isolation_level): i
            for i in range(1, num_threads + 1)
        }
        wait(futures)
    return time.time() - start_time

## Evaluate correctness
def check_correctness(conn: psycopg2.extensions.connection) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM accounts WHERE account = 0;")
        c2 = cur.fetchone()[0]
    c1 = 100
    return (c1 - c2) / 100.0

## Helper: one experiment run for a given (query, isolation, concurrency)
def run_experiment(conn: psycopg2.extensions.connection,
                          q_name: str, query: str,
                          isolation_name: str, iso_const: int,
                          max_concurrent: int, num_threads: int) -> None:
    create_table(conn)
    duration = run_transactions(num_threads, max_concurrent, query, iso_const)
    correctness = check_correctness(conn)
    throughput = num_threads / duration if duration > 0 else 0
    print(f"{q_name:<10} | {isolation_name:<15} | {max_concurrent:<10} | {throughput:<20.2f} | {correctness:.2f}")


## Run the transactions
def run_experiments() -> None:
    num_threads = 100
    main_conn = connect()

    levels = {
        "READ UNCOMMITTED": ISOLATION_LEVEL_READ_UNCOMMITTED,
        "READ COMMITTED": ISOLATION_LEVEL_READ_COMMITTED,
        "REPEATABLE READ": ISOLATION_LEVEL_REPEATABLE_READ,
        "SERIALIZABLE": ISOLATION_LEVEL_SERIALIZABLE
    }
    experiments = [(q_name, QUERIES[q_name], iso_name, iso_const)
                   for q_name in ("query_a", "query_b")
                   for iso_name, iso_const in levels.items()]

    print(f"{'Query':<10} | {'Isolation':<15} | {'Concurrent':<10} | {'Throughput (tx/s)':<20} | {'Correctness'}")
    print("-" * 80)

    for q_name, query, isolation_name, iso_const in experiments:
        for i in range(1, 6):
            run_experiment(main_conn, q_name, query, isolation_name, iso_const, i, num_threads)

    # Reset to default and run ANALYZE to refresh statistics
    main_conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED; ANALYZE;")

    disconnect(main_conn)


if __name__ == "__main__":
    run_experiments()
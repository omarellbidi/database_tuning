import time
import random
from db_config import get_connection

# SAMPLE DATA  
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

def run_throughput_test(query_type):
    conn = get_connection()
    cur = conn.cursor()
    
    query_count = 0
    start_time = time.time()
    
    print(f"Starting 65-second test for: {query_type}...")

    # Loop 65 sec for each query
    while time.time() - start_time < 65:
        if query_type == "POINT":
            val = random.choice(SAMPLE_PUBIDS)
            cur.execute("SELECT * FROM Publ WHERE pubID = %s", (val,))
        
        elif query_type == "LOW_SELECTIVITY":
            val = random.choice(SAMPLE_TITLES)
            cur.execute("SELECT * FROM Publ WHERE booktitle = %s", (val,))
            
        elif query_type == "IN_PREDICATE":
            vals = random.sample(SAMPLE_PUBIDS, 3) # Pick 3 unique IDs
            cur.execute("SELECT * FROM Publ WHERE pubID IN (%s, %s, %s)", (vals[0], vals[1], vals[2]))
            
        elif query_type == "HIGH_SELECTIVITY":
            val = random.choice(SAMPLE_YEARS)
            cur.execute("SELECT * FROM Publ WHERE year = %s", (val,))

        cur.fetchall() # Ensure data is actually retrieved
        query_count += 1

    # Calculating metrics AFTER the loop so it doesn't impact performance
    duration = time.time() - start_time
    avg_time = duration / query_count
    queries_per_sec = query_count / duration 
    
    print(f"DONE. Total Queries: {query_count}")
    print(f"Average Runtime: {avg_time:.6f} seconds")
    print(f"Queries per second: {queries_per_sec:.2f}\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    
    # UNCOMMENT ONE AT A TIME TO RUN THE TESTS
    
    # run_throughput_test("POINT")
    # run_throughput_test("LOW_SELECTIVITY")
    # run_throughput_test("IN_PREDICATE")
    # run_throughput_test("HIGH_SELECTIVITY")

import psycopg2
import psycopg2.extras
import os
from configparser import ConfigParser
from populate import populate_tsv
import time


def load_config(filename='conf.ini', section='postgresql') -> dict:
    parser = ConfigParser()
    parser.read(filename)

    # get section, default to postgresql
    config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            config[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return config


def connect(config: dict) -> any:
    """ Connect to the PostgreSQL database server """
    try:
        with psycopg2.connect(**config) as conn:
            print('Connected to the PostgreSQL server.')
            return conn
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def disconnect(conn: any) -> None:
    """ Disconnect from the PostgreSQL database server """
    if conn is not None:
        conn.close()
        print('Disconnected from the PostgreSQL server.')


# ------ Database schema ---------------------
def create_tables(conn: any) -> None:
    """
    Create tables with indices.
    Tables are renewed every time this function is called.
    """ 
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS employee;")
    cur.execute("CREATE TABLE employee (ssnum INT, name TEXT, manager TEXT, dept TEXT, salary INT, numfriends INT);")
    cur.execute("CREATE UNIQUE INDEX idx_ssnum_emp ON employee (ssnum);")
    cur.execute("CREATE UNIQUE INDEX idx_name_emp ON employee (name);")
    cur.execute("CREATE INDEX idx_dept_emp ON employee (dept);")
    
    cur.execute("DROP TABLE IF EXISTS student;")
    # We use german like grading system (1.0, 1.1, ..., 5.0)
    # where 1.0 is the best grade and 5.0 is the worst grade.
    cur.execute("CREATE TABLE student (ssnum INT,name TEXT,course TEXT,grade FLOAT);")
    cur.execute("CREATE UNIQUE INDEX idx_ssnum_stud ON student (ssnum);")
    cur.execute("CREATE UNIQUE INDEX idx_name_stud ON student (name);")
    
    cur.execute("DROP TABLE IF EXISTS techdept;")
    cur.execute("CREATE TABLE techdept (dept TEXT,manager TEXT,location TEXT);")
    cur.execute("CREATE UNIQUE INDEX idx_dept_tech ON techdept (dept);")
    
    conn.commit()
    print("Tables and indicies created successfully.")
    cur.close()


def insert_data(conn: any, employee_path="data/employee.tsv", student_path="data/student.tsv", techdept_path="data/techdept.tsv") -> None:
    cur = conn.cursor()
    data_dir = os.path.join(os.path.dirname(__file__) + "/data")

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    if len(os.listdir(data_dir)) == 0:
        print("No tsv files found. Generate data.")
        populate_tsv()

    cur.copy_expert("COPY employee FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', HEADER TRUE)", open(employee_path, "r", encoding="utf-8"))
    cur.copy_expert("COPY student FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', HEADER TRUE)", open(student_path, "r", encoding="utf-8"))    
    cur.copy_expert("COPY techdept FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', HEADER TRUE)", open(techdept_path, "r", encoding="utf-8"))

    conn.commit()
    print("Data inserted successfully.")
    cur.close()


# ------ Query analysis ---------------------------------------------------
# Fetch
def analyse_query(conn, query: str) -> dict:
    explain_sql = query

    with conn.cursor() as cur:
        cur.execute(explain_sql)
        rows = cur.fetchone()
    return rows[0][0]   # rows[0] = first row, [0] = first col (the JSON list); [0] = first plan object
 
 
# Node printer (recursive)
 
def print_node(node: dict, depth: int = 0) -> None:
    pad    = "    " * depth
    branch = "└── " if depth > 0 else ""
    vpd    = "    " * (depth + 1)          # property indent
 
    # Header
    node_type  = node.get("Node Type", "?")
    relation   = node.get("Relation Name", "")
    alias      = node.get("Alias", "")
    join_type  = node.get("Join Type", "")
    strategy   = node.get("Strategy", "")
    scan_dir   = node.get("Scan Direction", "")
    index_name = node.get("Index Name", "")
    parent_rel = node.get("Parent Relationship", "")
 
    header = node_type
    if strategy:   header += f"  [{strategy}]"
    if join_type:  header += f"  [{join_type}]"
    if scan_dir:   header += f"  [{scan_dir}]"
    if relation:   header += f"  on {relation}" + (f" as {alias}" if alias != relation else "")
    if index_name: header += f"  via {index_name}"
    if parent_rel: header += f"  ({parent_rel})"
 
    print(f"{pad}{branch}{header}")
 
    # Timing & rows
    print(f"{vpd}Cost:          {fmt_cost(node['Startup Cost'], node['Total Cost'])}")
    print(f"{vpd}Plan rows:     {node.get('Plan Rows', 'N/A'):,}  |  width={node.get('Plan Width', 'N/A')}")
    print(f"{vpd}Actual time:   startup={node.get('Actual Startup Time', 'N/A'):.3f} ms  "
          f"total={node.get('Actual Total Time', 'N/A'):.3f} ms")
    print(f"{vpd}Actual rows:   {node.get('Actual Rows', 'N/A')}  |  loops={node.get('Actual Loops', 1)}")
 
    # Conditions
    for key in ("Index Cond", "Filter", "Hash Cond", "Recheck Cond", "Join Filter"):
        if node.get(key):
            print(f"{vpd}{key+':':<15}{node[key]}")
 
    rows_removed = node.get("Rows Removed by Index Recheck") or node.get("Rows Removed by Filter")
    if rows_removed:
        print(f"{vpd}Rows removed:  {rows_removed}")
 
    if node.get("Index Searches") is not None:
        print(f"{vpd}Index searches:{node['Index Searches']}")
 
    # Buffer stats
    print(f"{vpd}Shared bufs:   {fmt_blocks(node, 'Shared')}")
    if any(node.get(f"Local {s} Blocks", 0) for s in ("Hit", "Read", "Dirtied", "Written")):
        print(f"{vpd}Local bufs:    {fmt_blocks(node, 'Local')}")
    if any(node.get(f"Temp {s} Blocks", 0) for s in ("Read", "Written")):
        print(f"{vpd}Temp bufs:     read={node.get('Temp Read Blocks',0)}  written={node.get('Temp Written Blocks',0)}")
 
    # Flags
    flags = []
    if node.get("Parallel Aware"): flags.append("Parallel Aware")
    if node.get("Async Capable"):  flags.append("Async Capable")
    if node.get("Disabled"):       flags.append("⚠ DISABLED")
    if flags:
        print(f"{vpd}Flags:         {', '.join(flags)}")
 
    # Recurse
    for child in node.get("Plans", []):
        print()
        print_node(child, depth + 1)
 
 
# ------- Report ---------------------
def report_analysis(report: dict, query_name: str, query: str) -> None:
    # Summary header
    print("=" * 62)
    print("  QUERY EXECUTION REPORT")
    print(f"  Query: {query_name}")
    print(f"  {query}")
    print("=" * 62)
    print(f"  Planning time:   {fmt_ms(report.get('Planning Time'))}")
    print(f"  Execution time:  {fmt_ms(report.get('Execution Time'))}")
 
    triggers = report.get("Triggers", [])
    if triggers:
        print(f"  Triggers fired:  {len(triggers)}")
        for t in triggers:
            print(f"    • {t.get('Trigger Name')}  calls={t.get('Calls')}  "
                  f"time={fmt_ms(t.get('Time'))}")
    else:
        print("  Triggers fired:  none")
 
    # Planning buffer usage
    planning = report.get("Planning", {})
    if planning:
        print()
        print("  Planning buffer usage:")
        print(f"    Shared: {fmt_blocks(planning, 'Shared')}")
 
    print("=" * 62)
    print()
 
    # Plan tree
    print("PLAN TREE")
    print("-" * 62)
    print_node(report["Plan"])
    print()


# ------ Optional / helper functions -----------------------
def report_elapsed_time_for(func: callable) -> None:
    start = time.time()
    func()
    end = time.time()
    print(f"Time taken to {func.__name__}: {end - start:.4f} seconds")

# Formatting helpers
def fmt_ms(value) -> str:
    return f"{value:.3f} ms" if value is not None else "N/A"
 
def fmt_cost(startup, total) -> str:
    return f"{startup:.2f} .. {total:.2f}"
 
def fmt_blocks(node: dict, prefix: str) -> str:
    hit     = node.get(f"{prefix} Hit Blocks", 0)
    read    = node.get(f"{prefix} Read Blocks", 0)
    dirtied = node.get(f"{prefix} Dirtied Blocks", 0)
    written = node.get(f"{prefix} Written Blocks", 0)
    return f"hit={hit}  read={read}  dirtied={dirtied}  written={written}"
    

# ------ Main functions -----------------------
def init_db(conn: any):
    """
    Create tables in the database,
    then read and insert data into the tables from tsv file.
    The data is randomly populated.
    If there is no tsv file, generate one.
    """
    create_tables(conn)
    insert_data(conn)


def report_query_analysis(conn: any) -> None:
    # Because some Python string formatting and concatenation can be incompatible with SQL, 
    # we use full SQL query to avoid the error.
    avg_query_bad = "EXPLAIN (ANALYZE, FORMAT JSON) SELECT AVG(salary) as avgsalary, dept FROM Employee GROUP BY dept HAVING dept = 'Tech1';" 
    avg_query_good = "EXPLAIN (ANALYZE, FORMAT JSON) SELECT AVG(salary) as avgsalary, dept FROM Employee WHERE dept = 'Tech1' GROUP BY dept;"
    index_use_query_bad = "EXPLAIN (ANALYZE, FORMAT JSON) SELECT Employee.ssnum FROM Employee WHERE Employee.name = 'Employee123' OR Employee.dept = 'NonTech1';"
    index_use_query_good ="EXPLAIN (ANALYZE, FORMAT JSON) SELECT Employee.ssnum FROM Employee WHERE Employee.name = 'Employee123' UNION SELECT Employee.ssnum FROM Employee WHERE Employee.dept = 'NonTech1';"

    print("Analysis of queries", "="*62)
    report_analysis(analyse_query(conn, avg_query_bad), "Average Query Bad", avg_query_bad)
    report_analysis(analyse_query(conn, avg_query_good), "Average Query Good", avg_query_good)

    report_analysis(analyse_query(conn, index_use_query_bad), "Index Use Query Bad", index_use_query_bad)
    report_analysis(analyse_query(conn, index_use_query_good), "Index Use Query Good", index_use_query_good)


if __name__ == "__main__":
    conn = connect(load_config())

    #init_db(conn) // Uncomment to create tables and insert data

    report_query_analysis(conn)
    
    disconnect(conn)






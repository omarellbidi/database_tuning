import mysql.connector
from populate import populate_tsv
import os
import json

# ------ Database connection -----------------
def connect() -> any:
    """ Connect to MariaDB database server """
    try:                                                                                                                
        return mysql.connector.connect(
                ssl_disabled=True,
                host="localhost",
                port=3306, 
                database="mariadb",
                user="kitajimamitsuhiro", 
                password = "")
    except (mysql.connector.Error, Exception) as error:
        print(error)


def disconnect(conn: any) -> None:
    """ Disconnect from the MariaDB database server """
    if conn is not None:
        conn.close()
        print('Disconnected from the MariaDB server.')


# ------ Database schema ---------------------
def create_tables(conn: any) -> None:
    """
    Create tables with indices if not exists.
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

    cur.fetchall()
    print("Tables and indicies created successfully.")
    cur.close()


def insert_data(conn: any, employee_path="data/employee.tsv", student_path="data/student.tsv", techdept_path="data/techdept.tsv") -> None:
    cur = conn.cursor()

    # The file path must be absolute for some reasons.
    employee_path_abs = os.path.join(os.path.dirname(__file__) + "/" + employee_path)
    student_path_abs = os.path.join(os.path.dirname(__file__) + "/" + student_path)
    techdept_path_abs = os.path.join(os.path.dirname(__file__) + "/" + techdept_path)
    
    data_dir = os.path.join(os.path.dirname(__file__) + "/data")

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    if len(os.listdir(data_dir)) == 0:
        print("No tsv files found. Generate data.")
        populate_tsv()

    # LOAD DATA LOCAL INFILE will be rejected on my environment (Macos, MariaDB server on brew)
    # Ignore header row.
    cur.execute("LOAD DATA INFILE %s INTO TABLE employee FIELDS TERMINATED BY '\t' IGNORE 1 LINES (ssnum, name, manager, dept, salary, numfriends);", (employee_path_abs,))
    cur.execute("LOAD DATA INFILE %s INTO TABLE student FIELDS TERMINATED BY '\t' IGNORE 1 LINES (ssnum, name, course, grade);", (student_path_abs,))
    cur.execute("LOAD DATA INFILE %s INTO TABLE techdept FIELDS TERMINATED BY '\t' IGNORE 1 LINES (dept, manager, location);", (techdept_path_abs,))
    
    conn.commit()
    print("Data inserted successfully.")
    cur.close()

# ------ Formatting helpers ------------------------------------------------------
def fmt_ms(value) -> str:
    return f"{value:.4f} ms" if value is not None else "N/A"
 
def fmt_cost(value) -> str:
    return f"{value:.7f}" if value is not None else "N/A"
 
 
# ------ Query plan analysis -------------------------------------------------------
def analyse_query(conn, query: str) -> dict:
    cur = conn.cursor()
    cur.execute(f"ANALYZE FORMAT=JSON {query}")
    rows = cur.fetchone()
    return json.loads(rows[0])
 
 
# ------ Node printer (recursive) --------------------------------------------------
def print_table(table: dict, depth: int) -> None:
    """Print a single table node."""
    pad  = "    " * depth
    vpd  = "    " * (depth + 1)
    branch = "└── " if depth > 0 else ""
 
    name        = table.get("table_name", "?")
    access_type = table.get("access_type", "")
    key         = table.get("key", "none")
    key_len     = table.get("key_length", "")
    possible    = ", ".join(table.get("possible_keys", []))
    used_parts  = ", ".join(table.get("used_key_parts", []))
    ref         = ", ".join(table.get("ref", []))
    loops       = table.get("loops", 1)
    r_loops     = table.get("r_loops", 1)
    rows        = table.get("rows", "N/A")
    r_rows      = table.get("r_rows", "N/A")
    cost        = table.get("cost")
    r_tbl_ms    = table.get("r_table_time_ms")
    r_other_ms  = table.get("r_other_time_ms")
    filtered    = table.get("filtered")
    r_filtered  = table.get("r_filtered")
    condition   = table.get("attached_condition", "")
    engine      = table.get("r_engine_stats", {})
 
    print(f"{pad}{branch}Table: {name}  [{access_type}]")
    print(f"{vpd}Key:           {key}" + (f"  (len={key_len})" if key_len else ""))
    if possible:
        print(f"{vpd}Possible keys: {possible}")
    if used_parts:
        print(f"{vpd}Used parts:    {used_parts}")
    if ref:
        print(f"{vpd}Ref:           {ref}")
    print(f"{vpd}Loops:         planned={loops}  actual={r_loops}")
    print(f"{vpd}Rows:          estimated={rows}  actual={r_rows}")
    print(f"{vpd}Cost:          {fmt_cost(cost)}")
    print(f"{vpd}Time:          table={fmt_ms(r_tbl_ms)}  other={fmt_ms(r_other_ms)}")
    if filtered is not None:
        print(f"{vpd}Filtered:      estimated={filtered}%  actual={r_filtered}%")
    if engine:
        pages = engine.get("pages_accessed", "N/A")
        print(f"{vpd}Engine stats:  pages_accessed={pages}")
    if condition:
        print(f"{vpd}Condition:     {condition}")
 
 
def print_nested_loop(nested_loop: list, depth: int) -> None:
    """Print all tables inside a nested_loop list."""
    for entry in nested_loop:
        table = entry.get("table")
        if table:
            print_table(table, depth)
 
 
def print_filesort(fs: dict, depth: int) -> None:
    """Print a filesort node and its children."""
    pad = "    " * depth
    vpd = "    " * (depth + 1)
    branch = "└── " if depth > 0 else ""
 
    sort_key   = fs.get("sort_key", "")
    r_loops    = fs.get("r_loops", 1)
    r_ms       = fs.get("r_total_time_ms")
    r_rows     = fs.get("r_output_rows")
    buf_size   = fs.get("r_buffer_size", "N/A")
    sort_mode  = fs.get("r_sort_mode", "N/A")
    prio_queue = fs.get("r_used_priority_queue", False)
 
    print(f"{pad}{branch}Filesort")
    print(f"{vpd}Sort key:      {sort_key}")
    print(f"{vpd}Loops:         {r_loops}")
    print(f"{vpd}Time:          {fmt_ms(r_ms)}")
    print(f"{vpd}Output rows:   {r_rows}")
    print(f"{vpd}Buffer size:   {buf_size}")
    print(f"{vpd}Sort mode:     {sort_mode}")
    print(f"{vpd}Priority queue:{prio_queue}")
 
    # Temporary table inside filesort
    tmp = fs.get("temporary_table", {})
    nested = tmp.get("nested_loop")
    if nested:
        print(f"{vpd}Temporary table → nested loop:")
        print_nested_loop(nested, depth + 2)
 
 
def print_nodes(node: dict, depth: int = 0) -> None:
    """Entry point — walks the top-level MariaDB ANALYZE JSON structure."""
    pad = "    " * depth
    vpd = "    " * (depth + 1)
 
    # query_block
    qb = node.get("query_block", {})
    if not qb:
        print(f"{pad}(empty plan)")
        return
 
    select_id  = qb.get("select_id", "?")
    cost       = qb.get("cost")
    r_loops    = qb.get("r_loops", 1)
    r_ms       = qb.get("r_total_time_ms")
 
    print(f"{pad}Query Block  (select_id={select_id})")
    print(f"{vpd}Cost:        {fmt_cost(cost)}")
    print(f"{vpd}Loops:       {r_loops}")
    print(f"{vpd}Total time:  {fmt_ms(r_ms)}")
    print()
 
    # Nested loop directly in query_block
    nested = qb.get("nested_loop")
    if nested:
        print_nested_loop(nested, depth + 1)
 
    # Filesort in query_block
    filesort = qb.get("filesort")
    if filesort:
        print_filesort(filesort, depth + 1)
 
    # TODO: Union / subqueries (extend here as needed)
    for key in ("union_result", "subquery", "duplicates_removal"):
        if qb.get(key):
            print("Warning: subquery, union, and duplicates_removal is not expanded")
            print(f"{vpd}[{key}]: (not expanded)")
            print(f"{vpd}  {qb[key]}")
 
 
# ------ Report --------------------------------------------------------------------
def report_analysis(report: dict, query_name: str, query: str) -> None:
    # Summary header
    print()
    print("=" * 62)
    print("  QUERY EXECUTION REPORT")
    print(f"  Query: {query_name}")
    print(f"  {query}")
    print("=" * 62)
 
    # Optimization time
    opt = report.get("query_optimization", {})
    if opt:
        print(f"  Optimization time: {fmt_ms(opt.get('r_total_time_ms'))}")
        print("-" * 62)
 
    # Plan tree
    print_nodes(report)
    print()
 
 

# ------ Main functions -----------------------
def init_db(conn: any) -> None:
    """
    Create tables in the database,
    then read and insert data into the tables from tsv file.
    The data is randomly populated.
    If there is no tsv file, generate one.
    """
    create_tables(conn)
    insert_data(conn)


# ------ Orchestrator --------------------------------------------------
def init_db(conn: any) -> None:
    create_tables(conn)
    insert_data(conn)


def report_query_analysis(conn: any) -> None:
    avg_query_bad = "SELECT AVG(salary) as avgsalary, dept FROM Employee GROUP BY dept HAVING dept = 'Tech1';" 
    avg_query_good = "SELECT AVG(salary) as avgsalary, dept FROM Employee WHERE dept = 'Tech1' GROUP BY dept;"
    
    join_query_bad = "SELECT * FROM employee INNER JOIN student ON (employee.name = student.name);"    
    join_query_good = "SELECT * FROM employee INNER JOIN student ON (employee.ssnum = student.ssnum);"

    print("Analysis of queries", "="*62)
    report_analysis(analyse_query(conn, avg_query_bad), "Average Query Bad", avg_query_bad)
    report_analysis(analyse_query(conn, avg_query_good), "Average Query Good", avg_query_good)

    report_analysis(analyse_query(conn, join_query_bad), "Join Query Bad", join_query_bad)
    report_analysis(analyse_query(conn, join_query_good), "Join Query Good", join_query_good)



if __name__ == "__main__":
    conn = connect()
    init_db(conn) # Uncomment to create tables and insert data
    report_query_analysis(conn)
    disconnect(conn)
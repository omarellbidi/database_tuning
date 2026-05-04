"""
task3.py – Index Tuning: Selection (Assignment 3)

Experiments covered:
  1. Clustered B+ Tree Index   (pubID)
  2. Non-Clustering B+ Tree Index (pubID)
  3. Non-Clustering Hash Index    (pubID)
  4. Table Scan                   (no index)

For every experiment we run four query shapes:
  • Point Query          – WHERE pubID = <value>
  • Multipoint (low)    – WHERE booktitle = <value>
  • Multipoint-IN (low) – WHERE pubID IN (<values>)
  • Multipoint (high)   – WHERE year = <value>

Each experiment is run REPETITIONS times per query to compute throughput
(queries / second).

Table name: "publication"  (the original dblp table is called "publ";
we rename it once at startup so that every query in this file can use the
canonical name "publication" throughout the assignment).
"""

import time
from configparser import ConfigParser
from typing import Any

import psycopg2
import psycopg2.extras


# ==============================================================================
# Config & connection helpers
# ==============================================================================

def load_config(filename: str = "conf.ini", section: str = "postgresql") -> dict:
    """
    Read database connection parameters from *filename*.

    Returns
    -------
    dict
        Keyword arguments suitable for psycopg2.connect().
    """
    parser = ConfigParser()
    parser.read(filename)

    if not parser.has_section(section):
        raise Exception(
            f"Section '{section}' not found in '{filename}'."
        )

    return dict(parser.items(section))


def connect(config: dict) -> Any:
    conn = psycopg2.connect(**config)
    print("Connected to PostgreSQL.")
    return conn


def disconnect(conn: Any) -> None:
    if conn is not None:
        conn.close()
        print("Disconnected from PostgreSQL.")


# ==============================================================================
# One-time setup: rename "publ" → "publication"
# ==============================================================================

def ensure_table_renamed(conn: Any) -> None:
    """
    Rename the table "publ" to "publication" if it has not been renamed yet.

    WHY: The more descriptive name "publication" makes queries self-documenting
    and avoids ambiguity with other objects. We guard with an existence check
    so the script is idempotent (safe to re-run after a restart).

    ALTER TABLE … RENAME TO is a purely metadata operation in PostgreSQL –
    no data is rewritten and it completes in milliseconds regardless of table size.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM   information_schema.tables
                WHERE  table_schema = 'public'
                AND    table_name   = 'publ'
            )
            """
        )
        publ_exists: bool = cur.fetchone()[0]

        if publ_exists:
            cur.execute("ALTER TABLE publ RENAME TO publication;")
            conn.commit()
            print("Table renamed: publ → publication.")
        else:
            print("Table 'publication' already exists – skipping rename.")


# ==============================================================================
# Statistics refresh
# ==============================================================================

def analyze_table(conn: Any) -> None:
    """
    Run ANALYZE on the 'publication' table to refresh planner statistics.

    WHY: After creating or dropping an index, or after CLUSTER physically
    reorders pages, the planner's statistics can be stale. Without fresh
    statistics the optimizer may choose a wrong plan. The assignment notes
    explicitly require ANALYZE after every change.

    WHY autocommit=True: ANALYZE is a utility command that must run outside
    a transaction block.
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("ANALYZE publication;")
    conn.autocommit = old_autocommit
    print("ANALYZE publication – statistics refreshed.")


# ==============================================================================
# Index management helpers
# ==============================================================================

def drop_index_if_exists(conn: Any, index_name: str) -> None:
    """
    Drop *index_name* if it exists; do nothing otherwise.

    WHY: Between experiments we always remove the previous index so that
    each experiment starts from a clean, index-free baseline. This prevents
    accidental plan re-use across experiment phases.

    WHY autocommit=True: DDL must not be nested inside a transaction.
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"DROP INDEX IF EXISTS {index_name};")
    conn.autocommit = old_autocommit
    print(f"Index '{index_name}' dropped (if it existed).")


def create_btree_index(conn: Any, index_name: str, column: str) -> None:
    """
    Create a non-clustering B+ tree index on *column* of 'publication'.

    WHY: A B+ tree supports both equality and range predicates. In the
    non-clustering variant the physical order of rows on disk does NOT match
    the index order, so each lookup may cause one random I/O per matching row.
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE INDEX {index_name} ON publication USING BTREE ({column});"
        )
    conn.autocommit = old_autocommit
    print(f"B+ tree index '{index_name}' created on column '{column}'.")


def create_hash_index(conn: Any, index_name: str, column: str) -> None:
    """
    Create a non-clustering hash index on *column* of 'publication'.

    WHY: A hash index stores a hash of each key and supports only equality
    predicates (=). PostgreSQL has supported crash-safe hash indexes since
    version 10 (WAL-logged).
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE INDEX {index_name} ON publication USING HASH ({column});"
        )
    conn.autocommit = old_autocommit
    print(f"Hash index '{index_name}' created on column '{column}'.")


def create_clustered_btree_index(conn: Any, index_name: str, column: str) -> None:
    """
    Create a B+ tree index on *column* and CLUSTER the table by it.

    WHY: A clustered index physically reorders heap pages so rows with
    adjacent key values are stored on the same or nearby pages. This reduces
    random I/Os for range and multipoint queries.

    WHY re-CLUSTER is needed: PostgreSQL does NOT maintain clustering
    automatically after INSERT/UPDATE, so we re-run CLUSTER at each
    experiment start.
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE INDEX {index_name} ON publication USING BTREE ({column});"
        )
        cur.execute(f"CLUSTER publication USING {index_name};")
    conn.autocommit = old_autocommit
    print(
        f"Clustered B+ tree index '{index_name}' created and "
        f"table clustered by '{column}'."
    )


def uncluster_table(conn: Any, index_name: str, shuffle_column: str = "pubID") -> None:
    """
    Remove the cluster association from 'publication' and drop the index.

    WHY: After each clustered-index sub-experiment we must undo the physical
    ordering before the next query shape is run. Otherwise heap pages remain
    sorted by the previously clustered column, giving artificially fast
    random-I/O behaviour to the next sub-experiment.

    WHY a different shuffle_column: re-clustering on the same column would
    leave the heap in the same order and defeat the purpose of unclustering.

    Parameters
    ----------
    conn           : active psycopg2 connection
    index_name     : name of the clustered index to drop
    shuffle_column : column used to re-cluster as a shuffle step; MUST differ
                     from the column that was just clustered.
    """
    old_autocommit = conn.autocommit
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE publication SET WITHOUT CLUSTER;")

        temp_idx = "publ_temp_shuffle_idx"
        cur.execute(
            f"CREATE INDEX {temp_idx} ON publication USING BTREE ({shuffle_column});"
        )
        cur.execute(f"CLUSTER publication USING {temp_idx};")
        cur.execute(f"DROP INDEX {temp_idx};")

        cur.execute(f"DROP INDEX IF EXISTS {index_name};")

    conn.autocommit = old_autocommit
    print(
        f"Table unclustered: physical order shuffled by '{shuffle_column}', "
        f"index '{index_name}' dropped."
    )


# ==============================================================================
# Query runners
# ==============================================================================

#: Number of times each query is repeated to compute throughput
REPETITIONS: int = 10


def run_queries(conn: Any, shape_label: str, queries: list[tuple[str, str]]) -> dict:
    """
    Execute each query in a shape block once and collect aggregate timings.

    Each query in the block uses a different predicate value so that no two
    repetitions share the same condition, avoiding plan-cache artifacts.

    Parameters
    ----------
    conn        : active psycopg2 connection
    shape_label : human-readable name for this shape block
    queries     : list of (label, sql) pairs – one per repetition

    Returns
    -------
    dict with keys:
        label        – shape block name
        times_ms     – list of per-query wall-clock times in milliseconds
        avg_ms       – average wall-clock time in milliseconds
        throughput   – queries per second  (1 / avg_seconds)
    """
    times_ms: list[float] = []

    for _label, sql in queries:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(sql)
            cur.fetchall()
            t1 = time.perf_counter()
        times_ms.append((t1 - t0) * 1_000)

    avg_ms: float = sum(times_ms) / len(times_ms)
    throughput: float = 1_000 / avg_ms if avg_ms > 0 else float("inf")

    return {
        "label": shape_label,
        "times_ms": times_ms,
        "avg_ms": avg_ms,
        "throughput": throughput,
    }


def get_explain_plan(conn: Any, sql: str) -> str:
    """
    Return the EXPLAIN ANALYZE output for *sql* as a formatted string.

    WHY EXPLAIN ANALYZE (not just EXPLAIN): it actually executes the query
    and reports both estimated costs and real runtime, as required by the
    assignment ("Use EXPLAIN ANALYZE for the query plans").

    Returns
    -------
    str
        Multi-line text representation of the query plan.
    """
    explain_sql = f"EXPLAIN ANALYZE {sql}"
    with conn.cursor() as cur:
        cur.execute(explain_sql)
        rows = cur.fetchall()
    return "\n".join(row[0] for row in rows)


# ==============================================================================
# Result printer
# ==============================================================================

def print_results(experiment_name: str, results: list[dict], plans: list[tuple[str, str]]) -> None:
    """
    Pretty-print timing results and pre-fetched EXPLAIN ANALYZE plans.

    WHY pre-fetched plans: EXPLAIN ANALYZE must be run while the index is
    still present (inside the per-shape loop in run_experiment). If called
    after the loop the index has already been dropped and the planner always
    falls back to a sequential scan, making every experiment look identical.

    Parameters
    ----------
    experiment_name : label for this experiment block (e.g. "Clustered B+ Tree")
    results         : output of run_queries()
    plans           : list of (sql, plan_text) pairs captured while the index
                      was live; plan_text is the raw EXPLAIN ANALYZE output
    """
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  EXPERIMENT: {experiment_name}")
    print(sep)
    print(f"  {'Query':<45} {'Avg (ms)':>10}  {'QPS':>10}")
    print(f"  {'-'*45} {'-'*10}  {'-'*10}")

    for r in results:
        print(f"  {r['label']:<45} {r['avg_ms']:>10.3f}  {r['throughput']:>10.2f}")

    print()

    for sql, plan_text in plans:
        print("  EXPLAIN ANALYZE plan for:", sql)
        print("-" * 70)
        for line in plan_text.splitlines():
            print("  " + line)
        print(sep)


# ==============================================================================
# Experiment definitions
# ==============================================================================

# WHY multiple predicate values: the assignment asks to "repeat the query
# multiple times with different conditions". We rotate through distinct values
# so the planner does not cache an identical result.

POINT_QUERY_IDS: list[str] = [
    "journals/acmcs/Codd79",
    "journals/cacm/Codd70",
    "conf/vldb/Gray79",
    "conf/sigmod/Stonebraker76",
    "conf/sigmod/DeWittG92",
    "conf/vldb/Mohan92",
    "journals/tods/BernsteinGM87",
    "conf/sosp/Lampson79",
    "books/mk/Gray93",
    "conf/sigmod/ChambersW76",
]

BOOKTITLE_VALUES: list[str] = [
    "VLDB",
    "SIGMOD Conference",
    "ICDE",
    "PODS",
    "EDBT",
    "DASFAA",
    "SSDBM",
    "CIDR",
    "DaMoN",
    "BTREE Workshop",
]

IN_PREDICATE_IDS: list[str] = [
    "journals/acmcs/Codd79",
    "journals/cacm/Codd70",
    "conf/vldb/Gray79",
    "conf/sigmod/Stonebraker76",
    "conf/sigmod/DeWittG92",
    "conf/vldb/Mohan92",
    "journals/tods/BernsteinGM87",
    "conf/sosp/Lampson79",
    "books/mk/Gray93",
    "conf/sigmod/ChambersW76",
    "journals/acmcs/Codd79",
    "conf/sigmod/DeWittG92",
    "journals/cacm/Codd70",
]

YEAR_VALUES: list[str] = ["1995", "1996", "1997", "1998", "1999", "2000", "2001", "2002", "2003", "2004"]


def get_query_shapes() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """
    Build four shape blocks, each containing REPETITIONS queries with
    different predicate values.

    Returns a list of 4 shape blocks:
        (shape_label, index_column, queries)
    where *queries* is a list of (label, sql) pairs.

    IN-clause queries use a sliding window of 3 consecutive IDs:
        IN (id[i], id[i+1], id[i+2])
    All other shapes use a single value at index i.
    """
    shapes: list[tuple[str, str, list[tuple[str, str]]]] = []

    # Shape block 1: Point Query – WHERE pubID = <value>
    point_queries = []
    for i in range(REPETITIONS):
        pid = POINT_QUERY_IDS[i]
        point_queries.append((
            f"Point Query (pubID='{pid}')",
            f"SELECT * FROM publication WHERE pubID = '{pid}';",
        ))
    shapes.append(("Point Query", "pubID", point_queries))

    # Shape block 2: Multipoint-low – WHERE booktitle = <value>
    booktitle_queries = []
    for i in range(REPETITIONS):
        bt = BOOKTITLE_VALUES[i]
        booktitle_queries.append((
            f"Multipoint-low (booktitle='{bt}')",
            f"SELECT * FROM publication WHERE booktitle = '{bt}';",
        ))
    shapes.append(("Multipoint-low", "booktitle", booktitle_queries))

    # Shape block 3: Multipoint-IN – WHERE pubID IN (i, i+1, i+2)
    in_queries = []
    for i in range(REPETITIONS):
        ids = IN_PREDICATE_IDS[i:i + 3]
        in_list = ", ".join(f"'{x}'" for x in ids)
        in_queries.append((
            f"Multipoint-IN ({len(ids)} pubIDs)",
            f"SELECT * FROM publication WHERE pubID IN ({in_list});",
        ))
    shapes.append(("Multipoint-IN", "pubID", in_queries))

    # Shape block 4: Multipoint-high – WHERE year = <value>
    year_queries = []
    for i in range(REPETITIONS):
        yr = YEAR_VALUES[i]
        year_queries.append((
            f"Multipoint-high (year='{yr}')",
            f"SELECT * FROM publication WHERE year = '{yr}';",
        ))
    shapes.append(("Multipoint-high", "year", year_queries))

    return shapes


from typing import Callable


def run_experiment(
    conn: Any,
    experiment_name: str,
    shapes: list[tuple[str, str, list[tuple[str, str]]]],
    create_index_fn: Callable[[Any, str, str], None],
    drop_index_fn:   Callable[[Any, str], None],
    base_idx_name:   str,
) -> list[dict]:
    """
    Execute one full experiment by iterating over each shape block.

    For every shape block the function:
      1. Creates the index on the block's *index_column*.
      2. Runs ANALYZE so the planner sees the new index.
      3. Captures the EXPLAIN ANALYZE plan for the first query in the block.
      4. Runs all REPETITIONS queries in the block (each with a unique condition).
      5. Drops the index so the next block starts from a clean baseline.
      6. Runs ANALYZE again so the planner sees the index is gone.

    Parameters
    ----------
    conn             : active psycopg2 connection
    experiment_name  : human-readable name printed in the report
    shapes           : list of (shape_label, index_column, queries) blocks
    create_index_fn  : function(conn, index_name, column) that creates the index
    drop_index_fn    : function(conn, index_name) that removes it
    base_idx_name    : prefix for generated index names

    Returns
    -------
    list of timing dicts (one per shape block)
    """
    results: list[dict]              = []
    plans:   list[tuple[str, str]]   = []

    for shape_label, index_column, queries in shapes:
        idx_name = f"{base_idx_name}_{index_column}"
        print(f"  > [{experiment_name}] indexing on '{index_column}' for: {shape_label}")

        create_index_fn(conn, idx_name, index_column)
        analyze_table(conn)

        plan_text = get_explain_plan(conn, queries[0][1])
        plans.append((queries[0][1], plan_text))

        timing = run_queries(conn, shape_label, queries)
        results.append(timing)

        drop_index_fn(conn, idx_name)
        analyze_table(conn)

    print_results(experiment_name, results, plans)
    return results


# ==============================================================================
# Main orchestration
# ==============================================================================

def main() -> None:
    """
    Entry point. Runs all four index experiments in sequence.

    For each experiment type (clustered B+ tree, non-clustering B+ tree,
    non-clustering hash, table scan) every query shape is measured
    individually with an index on its own condition column:

        Query shape          condition column   index column
        ─────────────────────────────────────────────────────
        Point Query          pubID = …          pubID
        Multipoint-low       booktitle = …      booktitle
        Multipoint-IN        pubID IN (…)       pubID
        Multipoint-high      year = …           year

    For each shape the lifecycle is:
        create index on condition column → ANALYZE → measure → drop index → ANALYZE
    """

    config = load_config("conf.ini")
    conn = connect(config)

    ensure_table_renamed(conn)

    shapes = get_query_shapes()

    # ========================================================================
    # EXPERIMENT 1 – Clustered B+ Tree Index
    # ========================================================================

    def create_clustered(conn: Any, idx_name: str, column: str) -> None:
        create_clustered_btree_index(conn, idx_name, column)

    def drop_clustered(conn: Any, idx_name: str) -> None:
        """
        WHY data-driven shuffle column: we query pg_index to find which column
        was just clustered, then pick a *different* shuffle column. Using the
        same column would leave the heap in the same physical order, making
        unclustering a no-op.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.attname
                FROM   pg_index     i
                JOIN   pg_attribute a ON a.attrelid = i.indrelid
                                      AND a.attnum = ANY(i.indkey)
                WHERE  i.indexrelid = %s::regclass
                LIMIT  1
                """,
                (idx_name,),
            )
            row = cur.fetchone()

        clustered_col = row[0] if row else "pubID"

        if clustered_col.lower() == "pubid":
            shuffle_col = "year"
        elif clustered_col.lower() == "year":
            shuffle_col = "pubID"
        else:
            shuffle_col = "pubID"   # safe default for booktitle etc.

        uncluster_table(conn, idx_name, shuffle_column=shuffle_col)

    print("\n>>> Experiment 1: Clustered B+ Tree Index")
    run_experiment(
        conn,
        "1 – Clustered B+ Tree Index",
        shapes,
        create_clustered,
        drop_clustered,
        base_idx_name="publ_clustered",
    )

    # ========================================================================
    # EXPERIMENT 2 – Non-Clustering B+ Tree Index
    # ========================================================================

    print("\n>>> Experiment 2: Non-Clustering B+ Tree Index")
    run_experiment(
        conn,
        "2 – Non-Clustering B+ Tree Index",
        shapes,
        create_btree_index,
        drop_index_if_exists,
        base_idx_name="publ_nc_btree",
    )

    # ========================================================================
    # EXPERIMENT 3 – Non-Clustering Hash Index
    # WHY: PostgreSQL hash indexes only support equality (=); the planner
    # may fall back to a seq scan for the IN-predicate shape.
    # ========================================================================

    print("\n>>> Experiment 3: Non-Clustering Hash Index")
    run_experiment(
        conn,
        "3 – Non-Clustering Hash Index",
        shapes,
        create_hash_index,
        drop_index_if_exists,
        base_idx_name="publ_nc_hash",
    )

    # ========================================================================
    # EXPERIMENT 4 – Table Scan (no index)
    # WHY disable index scans: even without a user-created index PostgreSQL
    # may use system indexes. Setting enable_indexscan=off and
    # enable_bitmapscan=off forces a sequential scan for the true baseline.
    # ========================================================================

    print("\n>>> Experiment 4: Table Scan (no index)")

    with conn.cursor() as cur:
        cur.execute("SET enable_indexscan  = off;")
        cur.execute("SET enable_bitmapscan = off;")
    conn.commit()

    def noop_create(conn: Any, idx_name: str, column: str) -> None:
        pass

    def noop_drop(conn: Any, idx_name: str) -> None:
        pass

    run_experiment(
        conn,
        "4 – Table Scan (no index)",
        shapes,
        noop_create,
        noop_drop,
        base_idx_name="publ_tablescan",   # unused but required by signature
    )

    with conn.cursor() as cur:
        cur.execute("SET enable_indexscan  = on;")
        cur.execute("SET enable_bitmapscan = on;")
    conn.commit()

    disconnect(conn)
    print("\nAll experiments completed.")


if __name__ == "__main__":
    main()

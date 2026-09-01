import duckdb
from pathlib import Path


CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "sales.csv"
ACTIVE_CSV_PATH=None



# ============================================================
# CONNECTION
# ============================================================
def set_active_dataset(file_path):
    global ACTIVE_CSV_PATH
    ACTIVE_CSV_PATH=Path(file_path)


def get_connection():

    if ACTIVE_CSV_PATH is None:
        raise RuntimeError("No dataset has been uploaded.")

    conn = duckdb.connect(":memory:")

    conn.execute(f"""
        CREATE TABLE dataset AS
        SELECT *
        FROM read_csv_auto('{ACTIVE_CSV_PATH.as_posix()}')
    """)

    return conn


# ============================================================
# QUALITY REPORT
# ============================================================

def get_quality_report():

    conn = get_connection()

    columns = conn.execute(
        "DESCRIBE dataset"
    ).fetchall()

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM dataset"
    ).fetchone()[0]

    duplicate_count = conn.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT *, COUNT(*) AS duplicate_count
            FROM dataset
            GROUP BY ALL
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    report = []

    for column in columns:

        column_name = column[0]
        data_type = column[1]

        null_count = conn.execute(
            f'''
            SELECT COUNT(*)
            FROM dataset
            WHERE "{column_name}" IS NULL
            '''
        ).fetchone()[0]

        null_percentage = (
            round((null_count / total_rows) * 100, 2)
            if total_rows > 0
            else 0
        )

        report.append({
            "column": column_name,
            "type": data_type,
            "null_count": null_count,
            "null_percentage": null_percentage
        })

    conn.close()

    return {
        "total_rows": total_rows,
        "duplicate_rows": duplicate_count,
        "columns": report
    }


# ============================================================
# CLEAN NUMERIC NULLS
# ============================================================

def clean_numeric_nulls(conn, columns):

    for column_name, data_type, *_ in columns:

        data_type = data_type.upper()

        if any(
            x in data_type
            for x in ["INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL"]
        ):

            conn.execute(f'''
                UPDATE dataset
                SET "{column_name}" = (
                    SELECT MEDIAN("{column_name}")
                    FROM dataset
                    WHERE "{column_name}" IS NOT NULL
                )
                WHERE "{column_name}" IS NULL
            ''')


# ============================================================
# CLEAN CATEGORICAL NULLS
# ============================================================

def clean_categorical_nulls(conn, columns):

    for column_name, data_type, *_ in columns:

        if "VARCHAR" in data_type.upper():

            conn.execute(f'''
                UPDATE dataset
                SET "{column_name}" = 'Unknown'
                WHERE "{column_name}" IS NULL
            ''')


# ============================================================
# HANDLE DUPLICATES
# ============================================================

def remove_duplicates(conn):

    conn.execute("""
        CREATE OR REPLACE TABLE dataset AS
        SELECT DISTINCT *
        FROM dataset
    """)


# ============================================================
# CLEAN DATASET
# ============================================================

def clean_dataset(conn):

    columns = conn.execute(
        "DESCRIBE dataset"
    ).fetchall()

    clean_numeric_nulls(conn, columns)

    clean_categorical_nulls(conn, columns)

    remove_duplicates(conn)

    return conn


# ============================================================
# SCHEMA
# ============================================================

def get_schema():

    conn = get_connection()

    result = conn.execute("""
        DESCRIBE dataset
    """).fetchall()

    conn.close()

    return result


# ============================================================
# EXECUTE QUERY
# ============================================================

def execute_query(query: str):

    conn = get_connection()

    result = conn.execute(query).fetchdf()

    conn.close()

    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    conn = get_connection()

    print("\n==============================")
    print("QUALITY BEFORE CLEANING")
    print("==============================")

    columns = conn.execute(
        "DESCRIBE dataset"
    ).fetchall()

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM dataset"
    ).fetchone()[0]

    print("Rows:", total_rows)

    for column_name, data_type, *_ in columns:

        null_count = conn.execute(
            f'''
            SELECT COUNT(*)
            FROM dataset
            WHERE "{column_name}" IS NULL
            '''
        ).fetchone()[0]

        print(
            f"{column_name}: "
            f"{null_count} NULL"
        )

    print("\n==============================")
    print("CLEANING DATASET")
    print("==============================")

    clean_dataset(conn)

    print("Cleaning complete.")

    print("\n==============================")
    print("QUERY RESULT")
    print("==============================")

    result = conn.execute("""
        SELECT
            Region,
            SUM(Sales) AS total_sales
        FROM dataset
        GROUP BY Region
        ORDER BY total_sales DESC
    """).fetchdf()

    print(result)

    conn.close()
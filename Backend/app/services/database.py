import duckdb
from pathlib import Path
CSV_PATH=Path(__file__).resolve().parents[2]/"data"/"sales.csv"

def get_connection():
    conn=duckdb.connect(":memory:")
    conn.execute(f"""
    CREATE TABLE sales AS 
    SELECT *
    FROM read_csv_auto('{CSV_PATH.as_posix()}')
""")
    return conn


def get_schema():
    conn=get_connection()
    result=conn.execute("""
    DESCRIBE sales
""").fetchall()
    conn.close()
    return result

def execute_query(query:str):
    conn=get_connection()
    result=conn.execute(query).fetchdf()
    conn.close()
    return result


if __name__=="__main__":
    print("Schema:")
    print(get_schema())
    print("\nQuery Result:")
    result=execute_query("""
    SELECT
            region,
            SUM(sales) AS total_sales
        FROM sales
        GROUP BY region
        ORDER BY total_sales DESC
""")
    print(result)


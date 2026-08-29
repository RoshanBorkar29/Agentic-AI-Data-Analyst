from app.tool.data_tool import inspect_dataset
from app.tool.sql_tool import run_sql

print("===Dataset====")
schema=inspect_dataset.invoke({})
print(schema)

print("===SQL===")

result=run_sql.invoke({
      "query": """
        SELECT
            region,
            SUM(sales) AS total_sales
        FROM sales
        GROUP BY region
        ORDER BY total_sales DESC
    """
})

print(result)
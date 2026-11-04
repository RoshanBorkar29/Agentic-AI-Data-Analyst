"""
Evaluation Dataset for Agentic AI Data Analyst

Each test case defines:
- id: Unique identifier
- category: Type of analytical question (aggregation, ranking, time_series, correlation, summary_metric, out_of_scope)
- question: The natural language prompt asked to the agent
- expected_valid: Whether the question is relevant to the dataset (tested by validate_question_node)
- expected_chart: Expected chart type ('bar', 'line', 'pie', 'histogram', 'scatter', 'none')
- ground_truth_sql: Canonical DuckDB SQL query against `dataset` (None if out_of_scope)
- description: Goal and expected behavior of the test case
"""

test_cases = [
    {
        "id": "TC_001",
        "category": "aggregation",
        "question": "What are total sales by region?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT Region, SUM(Sales) AS total_sales FROM dataset GROUP BY Region ORDER BY total_sales DESC",
        "description": "Category comparison: verifies multi-row grouping and bar chart selection."
    },
    {
        "id": "TC_002",
        "category": "ranking",
        "question": "Which region has the highest sales?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT Region, SUM(Sales) AS total_sales FROM dataset GROUP BY Region ORDER BY total_sales DESC LIMIT 1",
        "description": "Top-N ranking: checks sorting, limit handling, and comparative visualization."
    },
    {
        "id": "TC_003",
        "category": "time_series",
        "question": "Show monthly sales trends.",
        "expected_valid": True,
        "expected_chart": "line",
        "ground_truth_sql": "SELECT STRFTIME('%Y-%m', CAST(\"Order Date\" AS DATE)) AS month, SUM(Sales) AS total_sales FROM dataset GROUP BY month ORDER BY month",
        "description": "Temporal analysis: verifies date truncation/formatting and line chart selection."
    },
    {
        "id": "TC_004",
        "category": "aggregation",
        "question": "What are the total sales by category?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT Category, SUM(Sales) AS total_sales FROM dataset GROUP BY Category ORDER BY total_sales DESC",
        "description": "Categorical aggregation: tests grouping on Category with bar visualization."
    },
    {
        "id": "TC_005",
        "category": "ranking",
        "question": "Which product has the highest sales?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT \"Product Name\", SUM(Sales) AS total_sales FROM dataset GROUP BY \"Product Name\" ORDER BY total_sales DESC LIMIT 1",
        "description": "Quoted column name test: tests DuckDB handling of spaces in column 'Product Name'."
    },
    {
        "id": "TC_006",
        "category": "aggregation",
        "question": "What is the total profit by region?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT Region, SUM(Profit) AS total_profit FROM dataset GROUP BY Region ORDER BY total_profit DESC",
        "description": "Numeric aggregation on float column 'Profit' grouped by Region."
    },
    {
        "id": "TC_007",
        "category": "correlation",
        "question": "Show the relationship between sales and profit.",
        "expected_valid": True,
        "expected_chart": "scatter",
        "ground_truth_sql": "SELECT Sales, Profit FROM dataset LIMIT 100",
        "description": "Two continuous variables: tests scatter chart selection and numeric axis assignment."
    },
    {
        "id": "TC_008",
        "category": "summary_metric",
        "question": "What is the average sales value?",
        "expected_valid": True,
        "expected_chart": "none",
        "ground_truth_sql": "SELECT AVG(Sales) AS avg_sales FROM dataset",
        "description": "Scalar summary metric: single-number output where chart should be 'none'."
    },
    {
        "id": "TC_009",
        "category": "ranking",
        "question": "Which region generated the most profit?",
        "expected_valid": True,
        "expected_chart": "bar",
        "ground_truth_sql": "SELECT Region, SUM(Profit) AS total_profit FROM dataset GROUP BY Region ORDER BY total_profit DESC LIMIT 1",
        "description": "Profit ranking: verifies top-profit calculation and region identification."
    },
    {
        "id": "TC_010",
        "category": "time_series",
        "question": "How did sales change over time?",
        "expected_valid": True,
        "expected_chart": "line",
        "ground_truth_sql": "SELECT CAST(\"Order Date\" AS DATE) AS date, SUM(Sales) AS total_sales FROM dataset GROUP BY date ORDER BY date",
        "description": "Time-based trend: tests grouping by date and line chart selection."
    },
    {
        "id": "TC_011",
        "category": "out_of_scope",
        "question": "Who was the first president of the United States?",
        "expected_valid": False,
        "expected_chart": "none",
        "ground_truth_sql": None,
        "description": "Guardrail test: completely unrelated historical question; agent must flag question_valid=False."
    },
    {
        "id": "TC_012",
        "category": "out_of_scope",
        "question": "Can you write a python script to scrape a website?",
        "expected_valid": False,
        "expected_chart": "none",
        "ground_truth_sql": None,
        "description": "Guardrail test: generic coding prompt; agent must gracefully reject and not generate SQL."
    }
]
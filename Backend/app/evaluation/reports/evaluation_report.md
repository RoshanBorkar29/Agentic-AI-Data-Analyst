# Agentic AI Data Analyst - Evaluation Report

*Generated on: 2026-10-27 14:37:59*

## 1. Executive Scorecard

| Metric | Result | Description |
| :--- | :--- | :--- |
| **Overall Pass Rate** | **58.33%** (7/12) | Percentage of test cases passing all criteria |
| **SQL Execution Success** | **100.0%** | SQL ran without syntax/engine errors |
| **Pass@1 (First-Attempt SQL)** | **100.0%** | SQL succeeded on the first generation attempt |
| **Pass@2 (Self-Healing Recovery)** | **0.0%** | SQL recovered via error feedback loop |
| **Semantic Result Match** | **66.67%** | Numbers/data match Ground-Truth SQL query |
| **Chart Selection Accuracy** | **91.67%** | Agent selected the expected visualization type |
| **Question Guardrail Accuracy** | **100.0%** | Accurately accepts dataset queries / rejects out-of-scope |
| **Faithfulness Score** | **100.0%** | Percentage of cited text numbers backed by SQL results |

## 2. Latency & Performance

- **Average Latency:** 21.58 seconds
- **Median Latency:** 18.62 seconds
- **P95 Latency:** 55.3 seconds
- **Min / Max Latency:** 1.27s / 73.8s

## 3. Test Cases Breakdown

| ID | Category | Status | Latency | SQL OK | Chart Exp / Act | Data Match | Faithfulness |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `TC_001` | aggregation | ✅ PASS | 6.36s | ✅ | bar / bar | ✅ | 100% |
| `TC_002` | ranking | ✅ PASS | 5.45s | ✅ | bar / bar | ✅ | 100% |
| `TC_003` | time_series | ❌ FAIL | 8.77s | ✅ | line / line | ❌ | 100% |
| `TC_004` | aggregation | ❌ FAIL | 24.49s | ✅ | bar / bar | ❌ | 100% |
| `TC_005` | ranking | ❌ FAIL | 22.74s | ✅ | bar / none | ✅ | 100% |
| `TC_006` | aggregation | ✅ PASS | 18.37s | ✅ | bar / bar | ✅ | 100% |
| `TC_007` | correlation | ❌ FAIL | 73.8s | ✅ | scatter / scatter | ❌ | 100% |
| `TC_008` | summary_metric | ✅ PASS | 28.04s | ✅ | none / none | ✅ | 100% |
| `TC_009` | ranking | ✅ PASS | 18.88s | ✅ | bar / bar | ✅ | 100% |
| `TC_010` | time_series | ❌ FAIL | 40.17s | ✅ | line / line | ❌ | 100% |
| `TC_011` | out_of_scope | ✅ PASS | 10.67s | ✅ | none / none | ✅ | 100% |
| `TC_012` | out_of_scope | ✅ PASS | 1.27s | ✅ | none / none | ✅ | 100% |

## 4. Failure Analysis & Diagnostics

### Test Case `TC_003`: Show monthly sales trends.
- **Category:** time_series
- **Agent SQL:** `SELECT
    DATE_TRUNC('month', "Order Date") AS month,
    SUM(Sales) AS monthly_sales
FROM dataset
GROUP BY month
ORDER BY month;`
- **Reason:** Chart: line (exp: line) | Match: False

### Test Case `TC_004`: What are the total sales by category?
- **Category:** aggregation
- **Agent SQL:** `SELECT
    "Category",
    SUM("Sales") AS total_sales,
    SUM("Sales") / SUM(SUM("Sales")) OVER () AS category_share
FROM dataset
GROUP BY "Category"
ORDER BY total_sales DESC;`
- **Reason:** Chart: bar (exp: bar) | Match: False

### Test Case `TC_005`: Which product has the highest sales?
- **Category:** ranking
- **Agent SQL:** `SELECT
    "Product Name",
    SUM(Sales) AS total_sales
FROM dataset
GROUP BY "Product Name"
ORDER BY total_sales DESC
LIMIT 1;`
- **Reason:** Chart: none (exp: bar) | Match: True

### Test Case `TC_007`: Show the relationship between sales and profit.
- **Category:** correlation
- **Agent SQL:** `SELECT
    DATE_TRUNC('month', "Order Date") AS month,
    Category,
    SUM(Sales)  AS total_sales,
    SUM(Profit) AS total_profit,
    SUM(Profit) / NULLIF(SUM(Sales), 0) AS profit_margin
FROM dataset
GROUP BY month, Category
ORDER BY month, total_sales DESC;`
- **Reason:** Chart: scatter (exp: scatter) | Match: False

### Test Case `TC_010`: How did sales change over time?
- **Category:** time_series
- **Agent SQL:** `WITH sales_by_month AS (
    SELECT
        DATE_TRUNC('month', "Order Date") AS period,
        SUM(Sales) AS total_sales
    FROM dataset
    GROUP BY period
)
SELECT
    period,
    total_sales,
    total_sales - LAG(total_sales) OVER (ORDER BY period) AS sales_change,
    CASE
        WHEN LAG(total_sales) OVER (ORDER BY period) = 0 THEN NULL
        ELSE (total_sales - LAG(total_sales) OVER (ORDER BY period)) * 100.0
             / LAG(total_sales) OVER (ORDER BY period)
    END AS pct_change
FROM sales_by_month
ORDER BY period;`
- **Reason:** Chart: line (exp: line) | Match: False

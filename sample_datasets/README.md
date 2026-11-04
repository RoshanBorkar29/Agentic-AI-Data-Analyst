# Sample Datasets

This directory contains benchmark and demonstration datasets for the **Agentic AI Data Analyst** application.

---

## 1. `sales.csv` (Primary Benchmark Dataset)
- **Description:** Multi-region e-commerce/retail transaction dataset across several years.
- **Columns:**
  - `Order Date`: Transaction timestamp (`YYYY-MM-DD`)
  - `Product Name`: Specific item sold (e.g. Printer, Mouse, Tablet, Camera)
  - `Category`: Product sector (`Office`, `Accessories`, `Electronics`, etc.)
  - `Region`: Geographic sales region (`North`, `East`, `South`, `West`)
  - `Quantity`: Number of units purchased
  - `Sales`: Total gross sales revenue
  - `Profit`: Net profit earned
- **Recommended Test Questions:**
  - *"Which region generated the highest revenue?"*
  - *"Show monthly sales trends."*
  - *"Which products are underperforming in profit?"*
  - *"Generate SQL for this analysis."*
  - *"Detect anomalies in the dataset."*

---

## 2. `retail_sales_dataset.csv`
- **Description:** Customer transaction and demographic retail dataset.
- **Columns:**
  - `Transaction ID`: Unique receipt identifier
  - `Date`: Date of purchase
  - `Customer ID`: Customer identifier
  - `Gender`: Male / Female
  - `Age`: Customer age
  - `Product Category`: Beauty, Clothing, Electronics
  - `Quantity`: Items purchased
  - `Price per Unit`: Individual unit cost
  - `Total Amount`: Total cart value
- **Recommended Test Questions:**
  - *"What is the breakdown of sales by gender and age group?"*
  - *"Show the relationship between age and total spend."*
  - *"Which product category has the highest average order value?"*

---

## 3. `ecommerce_sales_data.csv`
- **Description:** Extended e-commerce dataset for testing multi-category volume and temporal shifts.


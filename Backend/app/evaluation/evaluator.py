"""
Automated Evaluation Harness for Agentic AI Data Analyst

Evaluates:
1. Question Relevance / Guardrail Rejection Accuracy
2. SQL Generation & Execution Success (Pass@1, Pass@2)
3. Semantic Result Equivalence (compares agent DuckDB result with ground-truth SQL result)
4. Chart Selection Accuracy (compares agent ChartSpec with expected visualization)
5. Numerical Faithfulness / Hallucination Detection (verifies cited numbers against data)
6. Latency & Performance Metrics
"""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import numpy as np
import pandas as pd

# Adjust module paths
CURRENT_DIR = Path(__file__).resolve().parent
APP_DIR = CURRENT_DIR.parent
BACKEND_DIR = APP_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agent.graph import graph
from app.evaluation.test_cases import test_cases
from app.services.database import get_connection, set_active_dataset

DATASET_PATH = BACKEND_DIR / "data" / "sales.csv"


# ============================================================
# HELPER: SEMANTIC RESULT COMPARISON
# ============================================================

def normalize_scalar(val: Any) -> Any:
    """Normalize numeric scalar for comparison."""
    if pd.isna(val):
        return None
    try:
        f = float(val)
        return round(f, 2)
    except (ValueError, TypeError):
        return str(val).strip().lower()


def compare_dataframes(df_agent: pd.DataFrame, df_gt: pd.DataFrame, tol: float = 0.05) -> Tuple[bool, str]:
    """
    Semantically compares two DataFrames produced by DuckDB.
    Handles different column naming and row ordering.
    """
    if df_agent.empty and df_gt.empty:
        return True, "Both results empty"
    if df_agent.empty != df_gt.empty:
        return False, f"Row count mismatch: agent={len(df_agent)}, gt={len(df_gt)}"

    # Check row counts
    if len(df_agent) != len(df_gt):
        return False, f"Row count mismatch: agent={len(df_agent)}, gt={len(df_gt)}"

    # Case 1: Single scalar comparison (e.g. COUNT, AVG, SUM)
    if df_gt.shape == (1, 1) and df_agent.shape == (1, 1):
        v_gt = df_gt.iloc[0, 0]
        v_ag = df_agent.iloc[0, 0]
        try:
            f_gt = float(v_gt)
            f_ag = float(v_ag)
            match = math.isclose(f_gt, f_ag, rel_tol=tol, abs_tol=tol)
            return match, f"Scalar check: gt={f_gt}, agent={f_ag}"
        except (ValueError, TypeError):
            match = str(v_gt).strip().lower() == str(v_ag).strip().lower()
            return match, f"Text scalar check: gt={v_gt}, agent={v_ag}"

    # Case 2: Multi-row or multi-column comparison
    try:
        # Separate numeric and string values from both dataframes
        def extract_values(df: pd.DataFrame) -> Tuple[List[float], List[str]]:
            nums = []
            strs = []
            for col in df.columns:
                for val in df[col]:
                    if pd.isna(val):
                        continue
                    try:
                        nums.append(float(val))
                    except (ValueError, TypeError):
                        strs.append(str(val).strip().lower())
            return sorted(nums), sorted(strs)

        agent_nums, agent_strs = extract_values(df_agent)
        gt_nums, gt_strs = extract_values(df_gt)

        # Check strings set (categories, names, regions)
        if len(agent_strs) != len(gt_strs):
            return False, f"Text values count mismatch: agent={len(agent_strs)}, gt={len(gt_strs)}"

        if agent_strs != gt_strs:
            return False, "String/Category labels mismatch"

        # Check numeric values with tolerance
        if len(agent_nums) != len(gt_nums):
            return False, f"Numeric values count mismatch: agent={len(agent_nums)}, gt={len(gt_nums)}"

        if agent_nums and gt_nums:
            if not np.allclose(agent_nums, gt_nums, rtol=tol, atol=tol):
                return False, "Numeric values mismatch within tolerance"

        return True, "Data values match ground truth"

    except Exception as e:
        return False, f"Comparison error: {str(e)}"


def check_sql_result_match(agent_sql: str, ground_truth_sql: str) -> Tuple[bool, str]:
    """Runs both queries in DuckDB and tests semantic equality."""
    if not agent_sql or not ground_truth_sql:
        return False, "Missing SQL query"

    conn = get_connection()
    try:
        gt_df = conn.execute(ground_truth_sql).fetchdf()
        agent_df = conn.execute(agent_sql).fetchdf()
        return compare_dataframes(agent_df, gt_df)
    except Exception as e:
        return False, f"Execution error: {str(e)}"
    finally:
        conn.close()


# ============================================================
# HELPER: FAITHFULNESS / HALLUCINATION CHECK
# ============================================================

def evaluate_faithfulness(findings: List[str], evidence: List[str], query_result: str) -> float:
    """
    Checks if numbers cited in the findings or evidence are grounded in the DuckDB query result.
    Returns faithfulness score from 0.0 to 1.0.
    """
    combined_text = " ".join(findings + evidence)
    # Extract floating or integer numbers (exclude single digits or small years if preferred)
    tokens = re.findall(r"(?<![A-Za-z])[-+]?\d*\.?\d+(?![A-Za-z])", combined_text)
    # Filter out empty or punctuation-only matches
    claimed_numbers = [t for t in tokens if len(t.strip()) > 0 and t != "."]

    if not claimed_numbers:
        return 1.0  # No numeric assertions were made

    grounded_count = 0
    # Clean query result string for simple containment check
    cleaned_result = re.sub(r"\s+", " ", query_result)

    for num in claimed_numbers:
        # Check direct substring
        if num in cleaned_result:
            grounded_count += 1
            continue
        # Check rounded integer if float was cited
        try:
            f = float(num)
            int_str = str(int(round(f)))
            if int_str in cleaned_result:
                grounded_count += 1
        except ValueError:
            pass

    return round(grounded_count / len(claimed_numbers), 2)


# ============================================================
# EVALUATION RUNNER
# ============================================================

class Evaluator:
    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path
        set_active_dataset(self.dataset_path)

    def evaluate_test_case(self, tc: Dict[str, Any]) -> Dict[str, Any]:
        tc_id = tc["id"]
        question = tc["question"]
        expected_valid = tc["expected_valid"]
        expected_chart = tc["expected_chart"]
        ground_truth_sql = tc.get("ground_truth_sql")

        initial_state = {
            "question": question,
            "schema": "",
            "data_quality": "",
            "sql_query": "",
            "query_result": "",
            "error": "",
            "sql_attempts": 0,
            "investigation_plan": "",
            "observations": "",
            "query_count": 0,
            "needs_second_investigation": False,
            "summary": "",
            "findings": [],
            "evidence": [],
            "recommendations": [],
            "chart": {},
            "final_answer": "",
        }

        start_time = time.perf_counter()
        try:
            result = graph.invoke(initial_state)
            latency = round(time.perf_counter() - start_time, 2)
            execution_crashed = False
            crash_reason = ""
        except Exception as e:
            latency = round(time.perf_counter() - start_time, 2)
            execution_crashed = True
            crash_reason = str(e)
            result = {}

        if execution_crashed:
            return {
                "id": tc_id,
                "category": tc["category"],
                "question": question,
                "status": "CRASHED",
                "latency_sec": latency,
                "guardrail_match": False,
                "sql_success": False,
                "pass_at_1": False,
                "pass_at_2": False,
                "chart_match": False,
                "result_match": False,
                "faithfulness": 0.0,
                "details": f"Execution crashed: {crash_reason}",
            }

        # 1. Guardrail / Validation match
        actual_valid = result.get("question_valid", True)
        guardrail_match = (actual_valid == expected_valid)

        # If question was expected to be rejected (out of scope)
        if not expected_valid:
            chart_type = result.get("chart", {}).get("type", "none") or "none"
            chart_match = (chart_type == "none")
            all_passed = guardrail_match and chart_match

            return {
                "id": tc_id,
                "category": tc["category"],
                "question": question,
                "status": "PASS" if all_passed else "FAIL",
                "latency_sec": latency,
                "guardrail_match": guardrail_match,
                "sql_success": True,  # Correctly skipped SQL
                "pass_at_1": True,
                "pass_at_2": False,
                "chart_match": chart_match,
                "result_match": True,  # Guardrail pass
                "faithfulness": 1.0,
                "agent_sql": "",
                "agent_chart": chart_type,
                "details": "Correctly rejected out-of-scope query" if guardrail_match else "Failed to reject out-of-scope query",
            }

        # 2. SQL Execution
        sql_query = result.get("sql_query", "")
        sql_error = result.get("error", "")
        attempts = result.get("sql_attempts", 0)
        sql_success = bool(sql_query) and (not sql_error or sql_error == "FINAL_ANALYSIS_ERROR")
        pass_at_1 = sql_success and (attempts == 1)
        pass_at_2 = sql_success and (attempts == 2)

        # 3. Chart Type Match
        agent_chart = result.get("chart", {}).get("type", "none") or "none"
        chart_match = (agent_chart.lower() == expected_chart.lower())

        # 4. Semantic Result Match (Data Correctness)
        result_match = False
        result_details = "N/A"
        if ground_truth_sql and sql_success:
            result_match, result_details = check_sql_result_match(sql_query, ground_truth_sql)
        elif not ground_truth_sql:
            result_match = True
            result_details = "No ground truth required"
        else:
            result_details = f"SQL error: {sql_error}"

        # 5. Faithfulness
        faithfulness = evaluate_faithfulness(
            result.get("findings", []),
            result.get("evidence", []),
            result.get("query_result", ""),
        )

        all_passed = guardrail_match and sql_success and chart_match and result_match

        return {
            "id": tc_id,
            "category": tc["category"],
            "question": question,
            "status": "PASS" if all_passed else "FAIL",
            "latency_sec": latency,
            "guardrail_match": guardrail_match,
            "sql_success": sql_success,
            "pass_at_1": pass_at_1,
            "pass_at_2": pass_at_2,
            "attempts": attempts,
            "chart_match": chart_match,
            "agent_chart": agent_chart,
            "expected_chart": expected_chart,
            "result_match": result_match,
            "result_details": result_details,
            "faithfulness": faithfulness,
            "agent_sql": sql_query,
            "details": f"Chart: {agent_chart} (exp: {expected_chart}) | Match: {result_match}",
        }

    def run_all(self, test_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        results = []
        total = len(test_list)

        print(f"\n{'='*70}")
        print(f"STARTING AGENTIC AI DATA ANALYST EVALUATION ({total} TEST CASES)")
        print(f"{'='*70}\n")

        for idx, tc in enumerate(test_list, 1):
            print(f"[{idx}/{total}] Running {tc['id']}: '{tc['question'][:45]}...'")
            eval_res = self.evaluate_test_case(tc)
            results.append(eval_res)

            status_tag = f"[{eval_res['status']}]"
            print(
                f"      -> {status_tag} Latency: {eval_res['latency_sec']}s | "
                f"SQL: {'OK' if eval_res['sql_success'] else 'ERR'} | "
                f"Chart: {eval_res.get('agent_chart', 'none')} | "
                f"Result Match: {'YES' if eval_res['result_match'] else 'NO'}"
            )

        summary = self._compute_summary(results)
        return results, summary

    def _compute_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(results)
        if total == 0:
            return {}

        pass_count = sum(1 for r in results if r["status"] == "PASS")
        guardrail_passes = sum(1 for r in results if r["guardrail_match"])
        sql_successes = sum(1 for r in results if r["sql_success"])
        pass_at_1_count = sum(1 for r in results if r["pass_at_1"])
        pass_at_2_count = sum(1 for r in results if r["pass_at_2"])
        chart_matches = sum(1 for r in results if r["chart_match"])
        result_matches = sum(1 for r in results if r["result_match"])
        avg_faithfulness = round(sum(r["faithfulness"] for r in results) / total * 100, 2)

        latencies = [r["latency_sec"] for r in results]
        avg_latency = round(np.mean(latencies), 2)
        median_latency = round(np.median(latencies), 2)
        p95_latency = round(np.percentile(latencies, 95), 2)
        min_latency = round(np.min(latencies), 2)
        max_latency = round(np.max(latencies), 2)

        return {
            "total_tests": total,
            "overall_passed": pass_count,
            "overall_pass_rate": round((pass_count / total) * 100, 2),
            "guardrail_accuracy": round((guardrail_passes / total) * 100, 2),
            "sql_execution_success_rate": round((sql_successes / total) * 100, 2),
            "pass_at_1_rate": round((pass_at_1_count / total) * 100, 2),
            "pass_at_2_recovery_rate": round((pass_at_2_count / total) * 100, 2),
            "chart_selection_accuracy": round((chart_matches / total) * 100, 2),
            "semantic_result_accuracy": round((result_matches / total) * 100, 2),
            "average_faithfulness": avg_faithfulness,
            "latency": {
                "avg_sec": avg_latency,
                "median_sec": median_latency,
                "p95_sec": p95_latency,
                "min_sec": min_latency,
                "max_sec": max_latency,
            },
        }


# ============================================================
# REPORT GENERATORS
# ============================================================

def generate_markdown_report(summary: Dict[str, Any], results: List[Dict[str, Any]], output_path: Path):
    """Writes a GitHub-flavored Markdown evaluation report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append(f"# Agentic AI Data Analyst - Evaluation Report\n")
    md.append(f"*Generated on: {timestamp}*\n")

    md.append("## 1. Executive Scorecard\n")
    md.append("| Metric | Result | Description |")
    md.append("| :--- | :--- | :--- |")
    md.append(f"| **Overall Pass Rate** | **{summary['overall_pass_rate']}%** ({summary['overall_passed']}/{summary['total_tests']}) | Percentage of test cases passing all criteria |")
    md.append(f"| **SQL Execution Success** | **{summary['sql_execution_success_rate']}%** | SQL ran without syntax/engine errors |")
    md.append(f"| **Pass@1 (First-Attempt SQL)** | **{summary['pass_at_1_rate']}%** | SQL succeeded on the first generation attempt |")
    md.append(f"| **Pass@2 (Self-Healing Recovery)** | **{summary['pass_at_2_recovery_rate']}%** | SQL recovered via error feedback loop |")
    md.append(f"| **Semantic Result Match** | **{summary['semantic_result_accuracy']}%** | Numbers/data match Ground-Truth SQL query |")
    md.append(f"| **Chart Selection Accuracy** | **{summary['chart_selection_accuracy']}%** | Agent selected the expected visualization type |")
    md.append(f"| **Question Guardrail Accuracy** | **{summary['guardrail_accuracy']}%** | Accurately accepts dataset queries / rejects out-of-scope |")
    md.append(f"| **Faithfulness Score** | **{summary['average_faithfulness']}%** | Percentage of cited text numbers backed by SQL results |")
    md.append("")

    lat = summary["latency"]
    md.append("## 2. Latency & Performance\n")
    md.append(f"- **Average Latency:** {lat['avg_sec']} seconds")
    md.append(f"- **Median Latency:** {lat['median_sec']} seconds")
    md.append(f"- **P95 Latency:** {lat['p95_sec']} seconds")
    md.append(f"- **Min / Max Latency:** {lat['min_sec']}s / {lat['max_sec']}s\n")

    md.append("## 3. Test Cases Breakdown\n")
    md.append("| ID | Category | Status | Latency | SQL OK | Chart Exp / Act | Data Match | Faithfulness |")
    md.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    for r in results:
        status_badge = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
        sql_badge = "✅" if r["sql_success"] else "❌"
        chart_str = f"{r.get('expected_chart', 'none')} / {r.get('agent_chart', 'none')}"
        data_badge = "✅" if r["result_match"] else "❌"
        faith_str = f"{int(r['faithfulness'] * 100)}%"

        md.append(
            f"| `{r['id']}` | {r['category']} | {status_badge} | {r['latency_sec']}s | {sql_badge} | {chart_str} | {data_badge} | {faith_str} |"
        )
    md.append("")

    # Failed cases details
    failed_cases = [r for r in results if r["status"] != "PASS"]
    if failed_cases:
        md.append("## 4. Failure Analysis & Diagnostics\n")
        for f in failed_cases:
            md.append(f"### Test Case `{f['id']}`: {f['question']}")
            md.append(f"- **Category:** {f['category']}")
            md.append(f"- **Agent SQL:** `{f.get('agent_sql', 'None')}`")
            md.append(f"- **Reason:** {f['details']}")
            md.append("")
    else:
        md.append("## 4. Failure Analysis & Diagnostics\n")
        md.append("🎉 **All test cases passed with zero failures!**\n")

    output_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[REPORT] Markdown report generated at: {output_path}")


# ============================================================
# CLI ENTRYPOINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Evaluate Agentic AI Data Analyst system.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test cases to run")
    parser.add_argument("--id", type=str, default=None, help="Run a specific test case by ID (e.g. TC_001)")
    parser.add_argument("--output-dir", type=str, default=str(CURRENT_DIR / "reports"), help="Output directory for reports")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    suite = test_cases
    if args.id:
        suite = [tc for tc in suite if tc["id"].upper() == args.id.upper()]
        if not suite:
            print(f"Error: Test case with id '{args.id}' not found.")
            sys.exit(1)

    if args.limit:
        suite = suite[: args.limit]

    evaluator = Evaluator(dataset_path=DATASET_PATH)
    results, summary = evaluator.run_all(suite)

    # Save JSON raw results
    json_path = out_dir / "evaluation_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    print(f"[REPORT] JSON results saved to: {json_path}")

    # Save Markdown report
    md_path = out_dir / "evaluation_report.md"
    generate_markdown_report(summary, results, md_path)

    print("\n" + "="*70)
    print("EVALUATION SUMMARY SCORECARD")
    print("="*70)
    print(f"Total Tests Run:              {summary['total_tests']}")
    print(f"Overall Passed:               {summary['overall_passed']} ({summary['overall_pass_rate']}%)")
    print(f"SQL Execution Success Rate:   {summary['sql_execution_success_rate']}%")
    print(f"Pass@1 Rate:                  {summary['pass_at_1_rate']}%")
    print(f"Pass@2 (Recovery) Rate:       {summary['pass_at_2_recovery_rate']}%")
    print(f"Semantic Result Accuracy:     {summary['semantic_result_accuracy']}%")
    print(f"Chart Selection Accuracy:     {summary['chart_selection_accuracy']}%")
    print(f"Question Guardrail Accuracy:  {summary['guardrail_accuracy']}%")
    print(f"Faithfulness Score:           {summary['average_faithfulness']}%")
    print(f"Average Latency:              {summary['latency']['avg_sec']}s (P95: {summary['latency']['p95_sec']}s)")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

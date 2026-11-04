from typing import Literal, TypedDict
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.services.database import get_quality_report, get_anomaly_report
from app.tool.data_tool import inspect_dataset
from app.tool.sql_tool import run_sql


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
load_dotenv()

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
    temperature=0,
)

json_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}},
)

class QuestionCheck(BaseModel):
    valid:bool


question_llm = llm.with_structured_output(QuestionCheck)

class ChartSpec(BaseModel):
    type: Literal["line", "bar", "pie", "histogram", "scatter", "none"]
    title: str
    x_axis: str | None
    y_axis: str | None
    data: list[dict]


class AnomalyItem(BaseModel):
    metric: str
    value: str
    expected_range: str
    severity: Literal["low", "medium", "high"] = "medium"
    reason: str


class FinalResult(BaseModel):
    summary: str
    findings: list[str]
    evidence: list[str]
    recommendations: list[str]
    chart: ChartSpec
    pandas_code: str | None = ""
    anomalies: list[AnomalyItem] | None = []
    reasoning: str | None = ""


class AgentState(TypedDict):
    question: str
    question_valid: bool
    session_id: str
    conversation_history: str
    schema: str
    data_quality: str
    sql_query: str
    pandas_code: str
    anomalies: list[dict]
    reasoning: str
    query_result: str
    error: str
    sql_attempts: int
    investigation_plan: str
    observations: str
    query_count: int
    needs_second_investigation: bool
    summary: str
    findings: list[str]
    evidence: list[str]
    recommendations: list[str]
    chart: dict
    final_answer: str


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


def clean_code(code: str) -> str:
    if not code:
        return ""
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

def validate_question_node(state:AgentState):
    history_ctx = state.get("conversation_history", "")
    history_part = f"\nRecent dialogue in this session:\n{history_ctx}\n" if history_ctx and history_ctx != "No previous conversation in this session." else ""
    prompt=f"""Determine whether the user's question can be answered using the uploaded dataset or refers to the ongoing conversation about it.
{history_part}
Question:
{state["question"]}

Return valid=true if the question asks about the dataset, its columns, values, statistics,
trends, comparisons, relationships, or is a conversational follow-up to prior turns in this session (e.g., "Show its trend", "Generate SQL for this analysis", "Why did that happen?", "Break it down by product").
Return valid=false for questions completely unrelated to the dataset or the session analysis.
Return only the structured result.
"""
    result=question_llm.invoke(prompt)
    return{
        "question_valid":result.valid
    }

def inspect_node(state: AgentState):
    quality = get_quality_report()
    anomaly_summary = get_anomaly_report()
    return {
        "schema": inspect_dataset.invoke({}),
        "data_quality": f"Quality Report: {quality}\nAnomaly Scan: {anomaly_summary}",
    }


def planning_node(state: AgentState):
    history_ctx = state.get("conversation_history", "")
    history_part = f"\nConversation Context (Previous Turns):\n{history_ctx}\n" if history_ctx and history_ctx != "No previous conversation in this session." else ""
    prompt = f"""Create a concise investigation plan for this data question.
{history_part}
Schema:
{state["schema"]}

Current Question:
{state["question"]}

Return at most two steps identifying the metric and any useful comparison. If the current question references prior turns (e.g. 'this analysis', 'its trends', 'that product'), resolve references using the conversation context."""
    return {"investigation_plan": llm.invoke(prompt).content.strip()}


def sql_generation_node(state: AgentState):
    history_ctx = state.get("conversation_history", "")
    history_part = f"\nConversation Context (Previous Turns in this Session):\n{history_ctx}\n" if history_ctx and history_ctx != "No previous conversation in this session." else ""
    prompt = f"""Write the next DuckDB SQL query for `dataset`.
{history_part}
Schema:
{state["schema"]}

Question:
{state["question"]}

Plan:
{state["investigation_plan"]}

Observations so far:
{state["observations"]}

Data quality & Anomaly scan:
{state["data_quality"]}

Rules:
- Use only `dataset` and schema columns; generate one read-only SELECT; prefer concise aggregations; never use SELECT *; limit output to rows needed for the question; handle NULLs when needed; use dataset dates, not CURRENT_DATE.
- When the question is a follow-up or asks to 'Generate SQL for this analysis', reference the metrics, entities, and filters established in the conversation context.
- When detecting anomalies or outliers: use statistical calculations in DuckDB such as mean and stddev (Z-score) or IQR (QUANTILE_CONT 0.25 and 0.75), filter rows where ABS(column - mean) > 2.5 * stddev or outside 1.5*IQR, select identifying attributes (e.g. date, category, name, region, value), and order by magnitude of deviation descending.
- Return only SQL."""
    return {"sql_query": clean_sql(llm.invoke(prompt).content), "sql_attempts": 0}


def execute_sql_node(state: AgentState):
    result = run_sql.invoke({"query": state["sql_query"]})
    attempts = state["sql_attempts"] + 1
    if result.startswith("SQL_ERROR:"):
        return {"query_result": "", "error": result, "sql_attempts": attempts}
    return {"query_result": result, "error": "", "sql_attempts": attempts}


def fix_sql_node(state: AgentState):
    prompt = f"""Correct this DuckDB SQL query.

Schema:
{state["schema"]}

SQL:
{state["sql_query"]}

Error:
{state["error"]}

Use only `dataset` and schema columns. Return one read-only SELECT query only."""
    return {"sql_query": clean_sql(llm.invoke(prompt).content)}


def analyze_result_node(state: AgentState):
    prompt = f"""Analyze this query result for the user's question.

Question:
{state["question"]}

Result:
{state["query_result"]}

Return 2-4 concise factual observations, no more than 50 words total. Do not repeat the SQL or schema. Then add exactly one final line: SECOND_QUERY: yes only if one more query is necessary to answer the question; otherwise SECOND_QUERY: no."""
    response = llm.invoke(prompt).content.strip()
    marker = "SECOND_QUERY:"
    observations, separator, decision = response.rpartition(marker)
    needs_second = separator != "" and decision.strip().lower().startswith("yes")
    observations = observations.strip() if separator else response
    previous = state["observations"].strip()
    return {
        "observations": f"{previous}\n{observations}".strip(),
        "query_count": state["query_count"] + 1,
        "needs_second_investigation": needs_second,
    }


def final_analysis_node(state: AgentState):
    prompt = f"""Answer the user's question using the observations and latest SQL result.

Question:
{state["question"]}

Observations:
{state["observations"]}

Latest SQL result:
{state["query_result"]}

Executed SQL:
{state["sql_query"]}

Return only valid JSON with exactly this structure:
{{
  "summary": "short summary",
  "findings": ["factual finding"],
  "evidence": ["number or comparison from the result"],
  "recommendations": ["recommendation supported by the result"],
  "chart": {{
    "type": "bar",
    "title": "Chart title",
    "x_axis": "column name",
    "y_axis": "column name",
    "data": []
  }},
  "pandas_code": "concise pandas code equivalent to the SQL analysis (assume df = pd.read_csv('...'))",
  "reasoning": "step-by-step analytical reasoning explaining how the data leads to these findings and recommendations",
  "anomalies": [
    {{
      "metric": "column or metric name",
      "value": "outlier value",
      "expected_range": "normal expected range or threshold",
      "severity": "high",
      "reason": "factual explanation of why this was flagged as an anomaly"
    }}
  ]
}}

Allowed chart types: line, bar, pie, histogram, scatter, none. Use only SQL-result values for the chart and use none when a chart is not useful. Do not invent facts, values, causes, or columns.
Chart rules:

- Use "bar" for comparing categories.
- Use "line" for values changing over time.
- Use "pie" only for part-to-whole proportions,percentage share.
- Use "scatter" only when comparing two numeric variables.
- Use "histogram" only for the distribution of one numeric variable.
- Use "none" when the question is not suitable for visualization.
- Never choose a chart type that cannot be created from the SQL result.

Anomaly rules:
- If the question asks to detect anomalies or outliers, or if anomalous rows/values were flagged in the observations or query result, populate the 'anomalies' array.
- For each flagged item, specify metric, value, expected_range, severity ('high', 'medium', or 'low'), and a clear explanation of why it was flagged.
- If no anomalies are investigated or present, return an empty array [] for 'anomalies'.
"""

    try:
        response = json_llm.invoke(prompt)
        result = FinalResult.model_validate_json(response.content)
    except Exception:
        return {
            "summary": "Unable to format the analysis response.",
            "findings": [],
            "evidence": [],
            "recommendations": [],
            "chart": {
                "type": "none",
                "title": "",
                "x_axis": None,
                "y_axis": None,
                "data": [],
            },
            "pandas_code": "",
            "anomalies": [],
            "reasoning": state.get("observations", ""),
            "error": "FINAL_ANALYSIS_ERROR",
        }

    anomalies_list = [a.model_dump() for a in (result.anomalies or [])]

    return {
        "summary": result.summary,
        "findings": result.findings,
        "evidence": result.evidence,
        "recommendations": result.recommendations,
        "chart": result.chart.model_dump(),
        "pandas_code": clean_code(result.pandas_code or ""),
        "anomalies": anomalies_list,
        "reasoning": result.reasoning or state.get("observations", ""),
    }


def answer_node(state: AgentState):
    if not state["question_valid"]:
        return {
            "summary": "This question is not related to the uploaded dataset.",
            "findings": [],
            "evidence": [],
            "recommendations": [],
            "chart": {},
            "sql_query": "",
            "pandas_code": "",
            "anomalies": [],
            "reasoning": "",
            "investigation_plan": "",
            "final_answer": (
                "I can only answer questions related to the uploaded dataset. "
                "Please ask a question about the data."
            )
        }

    if state["error"] == "FINAL_ANALYSIS_ERROR":
        return {
            "summary": "Unable to complete the analysis.",
            "findings": [],
            "evidence": [],
            "recommendations": [],
            "chart": {
                "type": "none",
                "title": "",
                "x_axis": None,
                "y_axis": None,
                "data": [],
            },
            "sql_query": state.get("sql_query", ""),
            "pandas_code": state.get("pandas_code", ""),
            "anomalies": [],
            "reasoning": state.get("observations", ""),
            "investigation_plan": state.get("investigation_plan", ""),
            "final_answer": (
                "The data was analyzed, but the final response could not be formatted. "
                "Please try the question again."
            ),
        }
    
    final_answer = f"""SUMMARY:
{state["summary"]}

FINDINGS:
{chr(10).join("- " + item for item in state["findings"])}

EVIDENCE:
{chr(10).join("- " + item for item in state["evidence"])}

RECOMMENDATIONS:
{chr(10).join("- " + item for item in state["recommendations"])}"""
    return {
        "final_answer": final_answer,
        "sql_query": state.get("sql_query", ""),
        "pandas_code": state.get("pandas_code", ""),
        "anomalies": state.get("anomalies", []),
        "reasoning": state.get("reasoning", state.get("observations", "")),
        "investigation_plan": state.get("investigation_plan", ""),
        "session_id": state.get("session_id", ""),
        "conversation_history": state.get("conversation_history", ""),
    }



def failure_node(state: AgentState):
    message = f"Unable to generate valid SQL after {state['sql_attempts']} attempts. Last error: {state['error']}"
    return {
        "summary": "Unable to answer the question.",
        "findings": [],
        "evidence": [],
        "recommendations": [],
        "chart": {"type": "none", "title": "", "x_axis": None, "y_axis": None, "data": []},
        "final_answer": message,
        "sql_query": state.get("sql_query", ""),
        "pandas_code": "",
        "anomalies": [],
        "reasoning": state.get("error", ""),
        "investigation_plan": state.get("investigation_plan", ""),
        "session_id": state.get("session_id", ""),
        "conversation_history": state.get("conversation_history", ""),
    }


def route_after_sql(state: AgentState):
    if not state["error"]:
        return "analyze"
    if state["sql_attempts"] < 2:
        return "fix_sql"
    return "failure"


def route_after_analysis(state: AgentState):
    if state["query_count"] < 2 and state["needs_second_investigation"]:
        return "continue"
    return "final_analysis"

def route_after_validation(state: AgentState):

    if state["question_valid"]:
        return "continue"

    return "answer"

builder = StateGraph(AgentState)
builder.add_node("validate_question",validate_question_node)
builder.add_node("inspect", inspect_node)
builder.add_node("plan", planning_node)
builder.add_node("generate_sql", sql_generation_node)
builder.add_node("execute_sql", execute_sql_node)
builder.add_node("fix_sql", fix_sql_node)
builder.add_node("analyze", analyze_result_node)
builder.add_node("final_analysis", final_analysis_node)
builder.add_node("answer", answer_node)
builder.add_node("failure", failure_node)
builder.add_edge(START, "inspect")
builder.add_edge("inspect", "validate_question")
builder.add_conditional_edges(
    "validate_question",
    route_after_validation,{
        "continue":"plan",
        "answer":"answer"
    }
)
builder.add_edge("plan", "generate_sql")
builder.add_edge("generate_sql", "execute_sql")
builder.add_conditional_edges(
    "execute_sql",
    route_after_sql,
    {"analyze": "analyze", "fix_sql": "fix_sql", "failure": "failure"},
)
builder.add_edge("fix_sql", "execute_sql")
builder.add_conditional_edges(
    "analyze",
    route_after_analysis,
    {"continue": "generate_sql", "final_analysis": "final_analysis"},
)
builder.add_edge("final_analysis", "answer")
builder.add_edge("answer", END)
builder.add_edge("failure", END)

graph = builder.compile()


if __name__ == "__main__":
    initial_state: AgentState = {
        "question": "What are the total sales per region?",
        "session_id": "test_session",
        "conversation_history": "",
        "schema": "",
        "data_quality": "",
        "sql_query": "",
        "pandas_code": "",
        "anomalies": [],
        "reasoning": "",
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

    result = graph.invoke(initial_state)

    print("FINAL SQL")
    print(result["sql_query"])
    print()
    print("FINAL QUERY RESULT")
    print(result["query_result"])
    print()
    print("FINAL ANSWER")
    print(result["final_answer"])
    print()
    print("CHART")
    print(result["chart"])
    print("finished!!")
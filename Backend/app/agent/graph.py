from typing import Literal, TypedDict
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.services.database import get_quality_report
from app.tool.data_tool import inspect_dataset
from app.tool.sql_tool import run_sql


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


class ChartSpec(BaseModel):
    type: Literal["line", "bar", "pie", "histogram", "scatter", "none"]
    title: str
    x_axis: str | None
    y_axis: str | None
    data: list[dict]


class FinalResult(BaseModel):
    summary: str
    findings: list[str]
    evidence: list[str]
    recommendations: list[str]
    chart: ChartSpec


class AgentState(TypedDict):
    question: str
    schema: str
    data_quality: str
    sql_query: str
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


def inspect_node(state: AgentState):
    return {
        "schema": inspect_dataset.invoke({}),
        "data_quality": str(get_quality_report()),
    }


def planning_node(state: AgentState):
    prompt = f"""Create a concise investigation plan for this data question.

Schema:
{state["schema"]}

Question:
{state["question"]}

Return at most two steps identifying the metric and any useful comparison."""
    return {"investigation_plan": llm.invoke(prompt).content.strip()}


def sql_generation_node(state: AgentState):
    prompt = f"""Write the next DuckDB SQL query for `dataset`.

Schema:
{state["schema"]}

Question:
{state["question"]}

Plan:
{state["investigation_plan"]}

Observations so far:
{state["observations"]}

Data quality:
{state["data_quality"]}

Rules: use only `dataset` and schema columns; generate one read-only SELECT; prefer concise aggregations; never use SELECT *; limit output to rows needed for the question; handle NULLs when needed; use dataset dates, not CURRENT_DATE. Return only SQL."""
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
  }}
}}

Allowed chart types: line, bar, pie, histogram, scatter, none. Use only SQL-result values for the chart and use none when a chart is not useful. Do not invent facts, values, causes, or columns."""
    result = FinalResult.model_validate_json(json_llm.invoke(prompt).content)
    return {
        "summary": result.summary,
        "findings": result.findings,
        "evidence": result.evidence,
        "recommendations": result.recommendations,
        "chart": result.chart.model_dump(),
    }


def answer_node(state: AgentState):
    final_answer = f"""SUMMARY:
{state["summary"]}

FINDINGS:
{chr(10).join("- " + item for item in state["findings"])}

EVIDENCE:
{chr(10).join("- " + item for item in state["evidence"])}

RECOMMENDATIONS:
{chr(10).join("- " + item for item in state["recommendations"])}"""
    return {"final_answer": final_answer}


def failure_node(state: AgentState):
    message = f"Unable to generate valid SQL after {state['sql_attempts']} attempts. Last error: {state['error']}"
    return {
        "summary": "Unable to answer the question.",
        "findings": [],
        "evidence": [],
        "recommendations": [],
        "chart": {"type": "none", "title": "", "x_axis": None, "y_axis": None, "data": []},
        "final_answer": message,
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


builder = StateGraph(AgentState)
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
builder.add_edge("inspect", "plan")
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
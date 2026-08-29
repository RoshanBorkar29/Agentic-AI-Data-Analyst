from typing import TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

from app.tool.data_tool import inspect_dataset
from app.tool.sql_tool import run_sql

import os


# -----------------------------
# Load environment variables
# -----------------------------

load_dotenv()

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
    temperature=0
)


# -----------------------------
# Agent State
# -----------------------------

class AgentState(TypedDict):
    question: str
    schema: str
    sql_query: str
    query_result: str
    error: str
    sql_attempts: int
    final_answer: str


# -----------------------------
# 1. Inspect Dataset
# -----------------------------

def inspect_node(state: AgentState):

    schema = inspect_dataset.invoke({})

    return {
        "schema": schema
    }


# -----------------------------
# 2. Generate SQL
# -----------------------------

def sql_generation_node(state: AgentState):

    prompt = f"""
You are an expert SQL data analyst.

You have access to a DuckDB table called `sales`.

Dataset schema:
{state["schema"]}

User question:
{state["question"]}

Your job is to determine whether the user's question
can be answered using the available dataset.

Rules:

1. Use ONLY the table `sales`.
2. Use ONLY columns that exist in the provided schema.
3. NEVER invent a table or column.
4. Generate ONLY read-only SELECT queries.
5. Do not use INSERT, UPDATE, DELETE, DROP, ALTER,
   CREATE or TRUNCATE.
6. The SQL must be compatible with DuckDB.
7. If the question cannot be answered using the available
   table or columns, return exactly:

UNSUPPORTED: <brief reason>

8. Otherwise return ONLY the SQL query.
"""

    response = llm.invoke(prompt)

    return {
        "sql_query": response.content.strip()
    }


# -----------------------------
# 3. Execute SQL
# -----------------------------

def execute_sql_node(state: AgentState):

    sql = state["sql_query"].strip()

    # Handle unsupported questions
    if sql.startswith("UNSUPPORTED:"):

        return {
            "query_result": "",
            "error": "",
            "sql_attempts": state["sql_attempts"]
        }

    result = run_sql.invoke({
        "query": sql
    })

    # SQL execution failed
    if result.startswith("SQL_ERROR:"):

        return {
            "query_result": "",
            "error": result,
            "sql_attempts": state["sql_attempts"] + 1
        }

    # SQL executed successfully
    return {
        "query_result": result,
        "error": "",
        "sql_attempts": state["sql_attempts"] + 1
    }


# -----------------------------
# 4. Fix SQL
# -----------------------------

def fix_sql_node(state: AgentState):

    prompt = f"""
You are an expert DuckDB SQL developer.

Dataset schema:
{state["schema"]}

User question:
{state["question"]}

Previous SQL:
{state["sql_query"]}

Database error:
{state["error"]}

Fix the SQL query.

Rules:

1. Use ONLY the `sales` table.
2. Use ONLY columns present in the schema.
3. NEVER invent columns.
4. Generate ONLY a SELECT query.
5. Do not modify the database.
6. Make the query compatible with DuckDB.
7. Return ONLY the corrected SQL query.
"""

    response = llm.invoke(prompt)

    return {
        "sql_query": response.content.strip()
    }


# -----------------------------
# 5. Generate Final Answer
# -----------------------------

def answer_node(state: AgentState):

    # Handle unsupported question
    if state["sql_query"].startswith("UNSUPPORTED:"):

        return {
            "final_answer": state["sql_query"]
        }

    prompt = f"""
You are a data analyst.

User question:
{state["question"]}

SQL query:
{state["sql_query"]}

Query result:
{state["query_result"]}

Answer the user's question using ONLY the query result.

Rules:
- Be concise.
- Include important numbers.
- Do not invent information.
- Do not claim anything that cannot be supported
  by the query result.
"""

    response = llm.invoke(prompt)

    return {
        "final_answer": response.content
    }


# -----------------------------
# 6. Failure Node
# -----------------------------

def failure_node(state: AgentState):

    return {
        "final_answer": (
            "I could not generate a valid SQL query after "
            f"{state['sql_attempts']} attempts.\n\n"
            f"Last error: {state['error']}"
        )
    }


# -----------------------------
# 7. Routing
# -----------------------------

def route_after_sql(state: AgentState):

    sql = state["sql_query"].strip()

    # User question cannot be answered
    if sql.startswith("UNSUPPORTED:"):
        return "answer"

    # SQL worked
    if state["error"] == "":
        return "answer"

    # Too many attempts
    if state["sql_attempts"] >= 2:
        return "failure"

    # Try fixing SQL
    return "fix_sql"


# -----------------------------
# Build Graph
# -----------------------------

builder = StateGraph(AgentState)

builder.add_node("inspect", inspect_node)
builder.add_node("generate_sql", sql_generation_node)
builder.add_node("execute_sql", execute_sql_node)
builder.add_node("fix_sql", fix_sql_node)
builder.add_node("answer", answer_node)
builder.add_node("failure", failure_node)


# -----------------------------
# Graph Edges
# -----------------------------

builder.add_edge(START, "inspect")

builder.add_edge(
    "inspect",
    "generate_sql"
)

builder.add_edge(
    "generate_sql",
    "execute_sql"
)

builder.add_conditional_edges(
    "execute_sql",
    route_after_sql,
    {
        "fix_sql": "fix_sql",
        "answer": "answer",
        "failure": "failure"
    }
)

builder.add_edge(
    "fix_sql",
    "execute_sql"
)

builder.add_edge(
    "answer",
    END
)

builder.add_edge(
    "failure",
    END
)


# -----------------------------
# Compile Graph
# -----------------------------

graph = builder.compile()


# -----------------------------
# Test
# -----------------------------

if __name__ == "__main__":

    result = graph.invoke({

        "question": "What are the total sales by region?",

        "schema": "",

        "sql_query": "",

        "query_result": "",

        "error": "",

        "sql_attempts": 0,

        "final_answer": ""
    })

    print("\n==============================")
    print("GENERATED SQL")
    print("==============================")
    print(result["sql_query"])

    print("\n==============================")
    print("QUERY RESULT")
    print("==============================")
    print(result["query_result"])

    print("\n==============================")
    print("FINAL ANSWER")
    print("==============================")
    print(result["final_answer"])
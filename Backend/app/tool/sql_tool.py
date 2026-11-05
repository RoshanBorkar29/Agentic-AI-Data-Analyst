from langchain_core.tools import tool
from app.services.database import execute_query
from langsmith import traceable

@tool
def run_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the sales dataset.
    Use this tool to retrieve analytical results.
    """
    try:
        query_upper = query.strip().upper()
        forbidden = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "TRUNCATE",
            "CREATE",
        ]
        for keyword in forbidden:
            if query_upper.startswith(keyword):
                return f"ERROR: {keyword} statements are not allowed."
        
        result = execute_query(query)

        if result.empty:
            return "Query executed successfully but returned no rows."
        
        # Guard against unbounded rows overwhelming LLM context window / Groq TPM limits
        MAX_ROWS_FOR_AGENT = 25
        if len(result) > MAX_ROWS_FOR_AGENT:
            preview = result.head(MAX_ROWS_FOR_AGENT).to_string(index=False)
            if len(preview) > 4000:
                preview = preview[:4000] + "\n... [TRUNCATED DUE TO COLUMN WIDTH]"
            return (
                f"{preview}\n\n"
                f"[NOTE: Truncated to top {MAX_ROWS_FOR_AGENT} rows for agent context out of {len(result)} total rows returned. "
                f"Total rows in result: {len(result)}]"
            )
        
        formatted = result.to_string(index=False)
        if len(formatted) > 4000:
            formatted = formatted[:4000] + "\n... [TRUNCATED DUE TO COLUMN WIDTH]"
        return formatted

    except Exception as e:
        return f"SQL_ERROR: {str(e)}"

from langchain_core.tools import tool
from app.services.database import execute_query

@tool
def run_sql(query:str)->str:
    """
    Execute a read-only SQL query against the sales dataset.
    Use this tool to retrieve analytical results.
    """
    try:
        query_upper=query.strip().upper()
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
        result=execute_query(query)

        if result.empty:
            return "Query executed successfully but returned no rows."
        return result.to_string(index=False)

    except Exception as e:
        return f"SQL_ERROR: {str(e)}"
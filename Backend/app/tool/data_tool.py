from langchain_core.tools import tool
from app.services.database import get_schema

@tool
def inspect_dataset() -> str:
    """
    Inspect the sales dataset and return its schema.
    Use this before generating SQL queries.
    """

    schema = get_schema()

    lines = []

    for column in schema:
        column_name = column[0]
        data_type = column[1]

        lines.append(f"- {column_name}: {data_type}")

    return "Dataset schema:\n" + "\n".join(lines)

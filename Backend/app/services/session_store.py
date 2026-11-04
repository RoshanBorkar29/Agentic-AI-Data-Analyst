"""
Session Store for Agentic AI Data Analyst
Maintains multi-turn conversation memory and context across analytical questions.
"""

from typing import Dict, List, Any
import time


class SessionManager:
    def __init__(self):
        # Maps session_id -> list of turn dicts
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}
        self._last_active: Dict[str, float] = {}

    def get_history(self, session_id: str, max_turns: int = 5) -> List[Dict[str, Any]]:
        """Returns the last N turns for the given session_id."""
        if not session_id or session_id not in self._sessions:
            return []
        return self._sessions[session_id][-max_turns:]

    def add_turn(
        self,
        session_id: str,
        question: str,
        summary: str = "",
        sql_query: str = "",
        findings: List[str] = None,
        evidence: List[str] = None
    ) -> None:
        """Records a completed turn in the session history."""
        if not session_id:
            return

        if session_id not in self._sessions:
            self._sessions[session_id] = []

        turn_data = {
            "turn_index": len(self._sessions[session_id]) + 1,
            "timestamp": time.time(),
            "question": question.strip(),
            "summary": summary.strip() if summary else "",
            "sql_query": sql_query.strip() if sql_query else "",
            "findings": findings or [],
            "evidence": evidence or []
        }

        self._sessions[session_id].append(turn_data)
        self._last_active[session_id] = time.time()

    def format_history_for_prompt(self, session_id: str, max_turns: int = 3) -> str:
        """Formats the most recent dialogue turns for prompt context."""
        history = self.get_history(session_id, max_turns=max_turns)
        if not history:
            return "No previous conversation in this session."

        formatted_turns = []
        for turn in history:
            idx = turn.get("turn_index", 1)
            q = turn.get("question", "")
            s = turn.get("summary", "")
            sql = turn.get("sql_query", "")
            
            entry = f"Turn {idx}:\n  User asked: \"{q}\""
            if sql:
                entry += f"\n  Query executed: {sql}"
            if s:
                entry += f"\n  Analysis result: {s}"
            formatted_turns.append(entry)

        return "\n\n".join(formatted_turns)

    def clear_session(self, session_id: str) -> bool:
        """Clears memory for a specific session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._last_active:
            del self._last_active[session_id]
        return True


# Global session manager instance
session_manager = SessionManager()


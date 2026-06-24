import json
import re
from typing import Any, Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_MODEL


DEFAULT_DOCUMENT_TYPES = {
    "listing_description",
    "viewing_note",
    "rental_note",
    "risk_note",
    "location_note",
}

SYSTEM_PROMPT = """
You plan retrieval queries for a Singapore property-analysis RAG system.

Return only valid JSON with this shape:
{
  "search_queries": ["query 1", "query 2"],
  "filters": {
    "status": "sample_shortlisted or null",
    "document_type": "one document type or null"
  },
  "intent": "short explanation of what evidence the retrieval should find"
}

Rules:
- Create 2 to 4 concise search queries.
- Expand vague phrases into property-analysis terms.
- Prefer notes about risk, rental, liquidity, resale, noise, vacancy, view, location, and yield when relevant.
- Use status "sample_shortlisted" only when the user asks about shortlisted properties.
- Use document_type only when the user clearly asks for one kind of note.
""".strip()


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _fallback_queries(message: str) -> List[str]:
    message_lower = message.lower()
    queries = [_clean_query(message)]

    if any(term in message_lower for term in ("risk", "red flag", "danger", "worry", "concern")):
        queries.append(
            "risk concern red flag liquidity overpaying vacancy noise weak resale low transaction volume"
        )

    if any(term in message_lower for term in ("yield", "rent", "rental", "tenant", "investment")):
        queries.append(
            "rental yield estimated rent tenant demand gross yield investment upside"
        )

    if any(term in message_lower for term in ("location", "mrt", "school", "amenity", "district")):
        queries.append(
            "location MRT schools amenities district accessibility neighbourhood convenience"
        )

    if any(term in message_lower for term in ("view", "layout", "floor", "noise", "renovation")):
        queries.append(
            "view layout floor level noise renovation condition facing viewing note"
        )

    deduped = []
    for query in queries:
        if query and query not in deduped:
            deduped.append(query)
    return deduped[:4]


def _fallback_document_type(message: str) -> Optional[str]:
    message_lower = message.lower()
    for document_type in DEFAULT_DOCUMENT_TYPES:
        normalized = document_type.replace("_", " ")
        if document_type in message_lower or normalized in message_lower:
            return document_type
    return None


def fallback_retrieval_plan(message: str, reason: Optional[str] = None) -> Dict[str, Any]:
    message_lower = message.lower()
    filters = {
        "status": "sample_shortlisted"
        if "shortlist" in message_lower or "shortlisted" in message_lower
        else None,
        "document_type": _fallback_document_type(message),
    }
    plan = {
        "search_queries": _fallback_queries(message),
        "filters": filters,
        "intent": "Local fallback query expansion.",
        "planner": "fallback",
    }
    if reason:
        plan["planner_error"] = reason
    return plan


def _parse_llm_plan(raw_text: str, message: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            return fallback_retrieval_plan(message, "LLM returned non-JSON output.")
        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return fallback_retrieval_plan(message, "LLM returned malformed JSON.")

    search_queries = parsed.get("search_queries") or []
    clean_queries = []
    for query in search_queries:
        if isinstance(query, str):
            clean_query = _clean_query(query)
            if clean_query and clean_query not in clean_queries:
                clean_queries.append(clean_query)

    if not clean_queries:
        clean_queries = _fallback_queries(message)

    filters = parsed.get("filters") or {}
    status = filters.get("status")
    if status != "sample_shortlisted":
        status = None

    document_type = filters.get("document_type")
    if document_type not in DEFAULT_DOCUMENT_TYPES:
        document_type = None

    return {
        "search_queries": clean_queries[:4],
        "filters": {
            "status": status,
            "document_type": document_type,
        },
        "intent": str(parsed.get("intent") or "LLM planned retrieval search."),
        "planner": "llm",
        "model": OPENAI_MODEL,
    }


def create_retrieval_plan(message: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return fallback_retrieval_plan(message, "OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except ImportError:
        return fallback_retrieval_plan(message, "The openai package is not installed.")

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=f"User question: {message}",
        )
        return _parse_llm_plan(response.output_text, message)
    except Exception as exc:
        return fallback_retrieval_plan(message, f"LLM planning failed: {exc}")

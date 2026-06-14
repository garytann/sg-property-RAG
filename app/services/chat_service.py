from collections import defaultdict
from typing import Any, Dict, List

from app.rag.retrieval import retrieve_context
from app.services.property_service import (
    get_property,
    list_properties,
)
from app.tools.calculations import calculate_property_metrics
from app.tools.ranking import rank_properties


def _explicitly_named_properties(
    conn,
    message: str,
) -> List[Dict[str, Any]]:
    message_lower = message.lower()
    properties = list_properties(conn, limit=200)
    return [
        property_row
        for property_row in properties
        if property_row["project_name"].lower() in message_lower
    ]


def _select_properties(
    conn,
    message: str,
    retrieved_context: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    named = _explicitly_named_properties(conn, message)
    if named:
        return named

    message_lower = message.lower()
    if "shortlist" in message_lower or "shortlisted" in message_lower:
        return list_properties(conn, status="sample_shortlisted", limit=50)

    property_ids = []
    for doc in retrieved_context:
        property_id = doc["property_id"]
        if property_id not in property_ids:
            property_ids.append(property_id)

    properties = []
    for property_id in property_ids[:5]:
        property_row = get_property(conn, property_id)
        if property_row:
            properties.append(property_row)

    if properties:
        return properties

    return list_properties(conn, status="sample_shortlisted", limit=5)


def _notes_by_property(
    docs: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        grouped[doc["property_id"]].append(doc)
    return grouped


def _format_money(value: float) -> str:
    return f"${value:,.0f}"


def _format_property_line(property_row: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    return (
        f"- {property_row['project_name']}: "
        f"asking {_format_money(property_row['asking_price'])}, "
        f"{property_row['floor_area_sqft']:,.0f} sqft, "
        f"PSF ${metrics['psf']:,.0f}, "
        f"gross yield {metrics['gross_yield_percent']:.2f}%"
    )


def _best_context_snippets(
    docs: List[Dict[str, Any]],
    property_id: str,
    limit: int = 3,
) -> List[str]:
    snippets = []
    for doc in docs:
        if doc["property_id"] != property_id:
            continue
        text = doc["text"].strip()
        if len(text) > 220:
            text = f"{text[:217]}..."
        snippets.append(f"{doc['document_type']}: {text}")
        if len(snippets) >= limit:
            break
    return snippets


def answer_chat(conn, message: str, top_k: int = 12) -> Dict[str, Any]:
    retrieved_context = retrieve_context(message, top_k=top_k)
    selected_properties = _select_properties(conn, message, retrieved_context)
    selected_ids = {property_row["id"] for property_row in selected_properties}
    selected_context = [
        doc for doc in retrieved_context if doc["property_id"] in selected_ids
    ]
    notes_by_property = _notes_by_property(selected_context)

    property_metrics = {
        property_row["id"]: calculate_property_metrics(property_row)
        for property_row in selected_properties
    }
    ranking = rank_properties(selected_properties, notes_by_property)

    lines = [
        "I compared the matching properties using the structured fields for price, floor area, and estimated rent, then pulled relevant notes/listing text for qualitative risks.",
        "",
        "Computed metrics:",
    ]
    for property_row in selected_properties:
        lines.append(_format_property_line(property_row, property_metrics[property_row["id"]]))

    if ranking:
        lines.extend(["", "Current ranking from this simple POC score:"])
        for index, item in enumerate(ranking, start=1):
            lines.append(
                f"{index}. {item['project_name']} "
                f"(score {item['investment_score']:.2f}, "
                f"yield {item['gross_yield_percent']:.2f}%, "
                f"risk score {item['risk_score']})"
            )

    lines.extend(["", "Relevant notes surfaced:"])
    has_snippets = False
    for property_row in selected_properties:
        snippets = _best_context_snippets(selected_context, property_row["id"])
        if not snippets:
            continue
        has_snippets = True
        lines.append(f"{property_row['project_name']}:")
        for snippet in snippets:
            lines.append(f"- {snippet}")

    if not has_snippets:
        lines.append("- No high-scoring notes matched the exact wording of the question. Try asking about rent, risk, location, noise, liquidity, or a specific project name.")

    lines.extend(
        [
            "",
            "Important: this is a learning POC. Treat the rent estimates and ranking as sample analysis until you replace them with verified transaction/rental data.",
        ]
    )

    sources = [
        {
            "id": doc["id"],
            "property_id": doc["property_id"],
            "project_name": doc["project_name"],
            "document_type": doc["document_type"],
            "score": doc["score"],
        }
        for doc in selected_context
    ]

    return {
        "answer": "\n".join(lines),
        "properties": selected_properties,
        "metrics": property_metrics,
        "ranking": ranking,
        "sources": sources,
    }

from typing import Any, Dict, Iterable, List

from app.tools.calculations import calculate_property_metrics


RISK_TERMS = {
    "concern",
    "risk",
    "overpaying",
    "vacancy",
    "liquidity",
    "slow",
    "noise",
    "weak",
    "compressed",
    "opportunity",
    "dated",
}


def estimate_note_risk_score(notes: Iterable[Dict[str, Any]]) -> int:
    score = 0
    for note in notes:
        text = (note.get("text") or note.get("note_text") or "").lower()
        note_type = note.get("document_type") or note.get("note_type")
        if note_type == "risk_note":
            score += 3
        score += sum(1 for term in RISK_TERMS if term in text)
    return score


def rank_properties(
    properties: List[Dict[str, Any]],
    notes_by_property: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    ranked = []
    for property_row in properties:
        metrics = calculate_property_metrics(property_row)
        risk_score = estimate_note_risk_score(notes_by_property.get(property_row["id"], []))
        investment_score = round(
            metrics["gross_yield_percent"] * 10 - risk_score,
            2,
        )
        ranked.append(
            {
                "property_id": property_row["id"],
                "project_name": property_row["project_name"],
                "investment_score": investment_score,
                "risk_score": risk_score,
                **metrics,
            }
        )

    ranked.sort(key=lambda item: item["investment_score"], reverse=True)
    return ranked


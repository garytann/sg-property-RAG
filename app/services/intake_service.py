import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.db.database import fetch_all, fetch_one


STRUCTURED_FIELDS = {
    "source_url",
    "project_name",
    "district",
    "address",
    "property_type",
    "tenure",
    "top_year",
    "asking_price",
    "floor_area_sqft",
    "bedrooms",
    "bathrooms",
    "floor_level",
    "monthly_rent_estimate",
    "listing_description",
    "status",
}

ANALYSIS_FIELDS = [
    "asking_price",
    "floor_area_sqft",
    "bedrooms",
    "monthly_rent_estimate",
    "tenure",
    "top_year",
    "district",
]

VALID_NOTE_TYPES = {
    "viewing_note",
    "risk_note",
    "rental_note",
    "location_note",
    "valuation_note",
    "general_note",
}

INTAKE_SYSTEM_PROMPT = """
You extract structured property intake data from a user's messy Singapore property note.

Return only valid JSON with this shape:
{
  "property_identity": {
    "project_name": "string or null",
    "address": "string or null",
    "source_url": "string or null"
  },
  "structured_fields": {
    "district": 15,
    "property_type": "Condo",
    "tenure": "99-year leasehold",
    "top_year": 2024,
    "asking_price": 1600000,
    "floor_area_sqft": 721,
    "bedrooms": 2,
    "bathrooms": 2,
    "floor_level": "high floor",
    "monthly_rent_estimate": 5200,
    "listing_description": "string or null",
    "status": "user_intake_partial"
  },
  "notes": [
    {
      "note_type": "viewing_note",
      "note_text": "specific observation from the user"
    }
  ],
  "confidence": 0.0,
  "missing_fields": ["asking_price"],
  "follow_up_questions": ["What is the asking price?"]
}

Rules:
- Do not invent missing values.
- Use null for unknown structured fields.
- Keep user observations as notes.
- Use note_type values from: viewing_note, risk_note, rental_note, location_note, valuation_note, general_note.
- Mark status as user_intake_partial unless the user clearly provided a complete listing.
- Ask only the most useful follow-up questions, up to 4.
""".strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_money(value: str) -> Optional[float]:
    cleaned = value.lower().replace(",", "").replace("$", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(m|mil|million|k)?", cleaned)
    if not match:
        return None

    amount = float(match.group(1))
    suffix = match.group(2)
    if suffix in {"m", "mil", "million"}:
        amount *= 1_000_000
    elif suffix == "k":
        amount *= 1_000
    return amount


def _extract_project_name(message: str) -> Optional[str]:
    patterns = [
        r"\b(?:viewed|viewing|saw|visited|shortlisted|considering)\s+([A-Z][A-Za-z0-9 @'&.-]+)",
        r"\b(?:at|for)\s+([A-Z][A-Za-z0-9 @'&.-]+)",
    ]
    stop_words = {
        "nice",
        "asking",
        "agent",
        "road",
        "noise",
        "unit",
        "was",
        "but",
        "with",
        "around",
    }
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if not match:
            continue
        candidate = re.split(r"[,.]", match.group(1).strip())[0]
        words = []
        for word in candidate.split():
            if word.lower() in stop_words:
                break
            words.append(word)
        project_name = " ".join(words).strip()
        if project_name:
            return project_name
    return None


def _classify_note_type(message: str) -> str:
    message_lower = message.lower()
    if any(term in message_lower for term in ("rent", "tenant", "yield")):
        return "rental_note"
    if any(term in message_lower for term in ("risk", "red flag", "overpay", "vacancy", "liquidity")):
        return "risk_note"
    if any(term in message_lower for term in ("mrt", "school", "amenity", "location", "district")):
        return "location_note"
    if any(term in message_lower for term in ("price", "psf", "asking", "valuation")):
        return "valuation_note"
    if any(term in message_lower for term in ("view", "viewed", "layout", "noise", "renovation", "condition")):
        return "viewing_note"
    return "general_note"


def _fallback_extract(message: str) -> Dict[str, Any]:
    message_lower = message.lower()
    identity = {
        "project_name": _extract_project_name(message),
        "address": None,
        "source_url": None,
    }
    url_match = re.search(r"https?://\S+", message)
    if url_match:
        identity["source_url"] = url_match.group(0).rstrip(".,)")

    fields: Dict[str, Any] = {
        "district": None,
        "property_type": None,
        "tenure": None,
        "top_year": None,
        "asking_price": None,
        "floor_area_sqft": None,
        "bedrooms": None,
        "bathrooms": None,
        "floor_level": None,
        "monthly_rent_estimate": None,
        "listing_description": None,
        "status": "user_intake_partial",
    }

    district_match = re.search(r"\b(?:d|district)\s*(\d{1,2})\b", message_lower)
    if district_match:
        fields["district"] = int(district_match.group(1))

    sqft_match = re.search(r"(\d{3,5}(?:,\d{3})?)\s*(?:sqft|sq ft|square feet)", message_lower)
    if sqft_match:
        fields["floor_area_sqft"] = float(sqft_match.group(1).replace(",", ""))

    bed_match = re.search(r"(\d+)\s*(?:bed|br|bedroom)", message_lower)
    if bed_match:
        fields["bedrooms"] = int(bed_match.group(1))

    bath_match = re.search(r"(\d+)\s*(?:bath|bathroom)", message_lower)
    if bath_match:
        fields["bathrooms"] = int(bath_match.group(1))

    price_match = re.search(r"(?:asking|price|seller wants|around|about)\s*(?:is|at|around|about)?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?\s*(?:m|mil|million|k)?)", message_lower)
    if price_match:
        fields["asking_price"] = _parse_money(price_match.group(1))

    rent_match = re.search(r"(?:rent|rental)\s*(?:estimate|is|at|around|about)?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k)?)", message_lower)
    if rent_match:
        fields["monthly_rent_estimate"] = _parse_money(rent_match.group(1))

    top_match = re.search(r"\btop\s*(?:year)?\s*(\d{4})\b", message_lower)
    if top_match:
        fields["top_year"] = int(top_match.group(1))

    if "freehold" in message_lower:
        fields["tenure"] = "Freehold"
    else:
        tenure_match = re.search(r"(\d{2,3})\s*[- ]?year", message_lower)
        if tenure_match:
            fields["tenure"] = f"{tenure_match.group(1)}-year leasehold"

    for floor_level in ("high floor", "mid floor", "low floor", "ground floor"):
        if floor_level in message_lower:
            fields["floor_level"] = floor_level
            break

    notes = [
        {
            "note_type": _classify_note_type(message),
            "note_text": message.strip(),
        }
    ]

    return {
        "property_identity": identity,
        "structured_fields": fields,
        "notes": notes,
        "confidence": 0.45,
    }


def _parse_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _llm_extract(message: str) -> Optional[Dict[str, Any]]:
    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=INTAKE_SYSTEM_PROMPT,
            input=f"User property intake:\n{message}",
        )
        return _parse_llm_json(response.output_text)
    except Exception:
        return None


def _normalize_extraction(extraction: Dict[str, Any], message: str) -> Dict[str, Any]:
    fallback = _fallback_extract(message)
    identity = extraction.get("property_identity") or {}
    fields = extraction.get("structured_fields") or {}

    normalized_identity = {
        "project_name": identity.get("project_name") or fallback["property_identity"]["project_name"],
        "address": identity.get("address") or fallback["property_identity"]["address"],
        "source_url": identity.get("source_url") or fallback["property_identity"]["source_url"],
    }

    normalized_fields = {}
    for field in STRUCTURED_FIELDS:
        if field in {"project_name", "address", "source_url"}:
            continue
        value = fields.get(field)
        if value is None:
            value = fallback["structured_fields"].get(field)
        normalized_fields[field] = value

    notes = []
    for note in extraction.get("notes") or fallback["notes"]:
        note_text = str(note.get("note_text") or "").strip()
        note_type = note.get("note_type")
        if note_type not in VALID_NOTE_TYPES:
            note_type = "general_note"
        if note_text:
            notes.append({"note_type": note_type, "note_text": note_text})

    if not notes:
        notes = fallback["notes"]

    return {
        "property_identity": normalized_identity,
        "structured_fields": normalized_fields,
        "notes": notes,
        "confidence": float(extraction.get("confidence") or fallback["confidence"]),
    }


def _find_matching_property(conn, identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    project_name = identity.get("project_name")
    if not project_name:
        return None

    exact = fetch_one(
        conn,
        "SELECT * FROM properties WHERE LOWER(project_name) = LOWER(%s) LIMIT 1",
        [project_name],
    )
    if exact:
        return exact

    return fetch_one(
        conn,
        """
        SELECT * FROM properties
        WHERE LOWER(project_name) LIKE LOWER(%s)
        ORDER BY project_name
        LIMIT 1
        """,
        [f"%{project_name}%"],
    )


def _non_empty_fields(identity: Dict[str, Any], fields: Dict[str, Any]) -> Dict[str, Any]:
    values = {
        "project_name": identity.get("project_name"),
        "address": identity.get("address"),
        "source_url": identity.get("source_url"),
        **fields,
    }
    return {
        key: value
        for key, value in values.items()
        if key in STRUCTURED_FIELDS and value not in (None, "")
    }


def _create_property_shell(conn, identity: Dict[str, Any], fields: Dict[str, Any]) -> Optional[str]:
    if not any(identity.get(field) for field in ("project_name", "address", "source_url")):
        return None

    property_id = _new_id("prop_user")
    now = _now()
    project_name = identity.get("project_name") or identity.get("address") or identity.get("source_url")
    values = {
        "id": property_id,
        "source_url": identity.get("source_url"),
        "project_name": project_name,
        "district": fields.get("district"),
        "address": identity.get("address"),
        "property_type": fields.get("property_type"),
        "tenure": fields.get("tenure"),
        "top_year": fields.get("top_year"),
        "asking_price": fields.get("asking_price"),
        "floor_area_sqft": fields.get("floor_area_sqft"),
        "bedrooms": fields.get("bedrooms"),
        "bathrooms": fields.get("bathrooms"),
        "floor_level": fields.get("floor_level"),
        "monthly_rent_estimate": fields.get("monthly_rent_estimate"),
        "listing_description": fields.get("listing_description"),
        "status": fields.get("status") or "user_intake_partial",
        "created_at": now,
    }

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO properties (
                id, source_url, project_name, district, address, property_type,
                tenure, top_year, asking_price, floor_area_sqft, bedrooms,
                bathrooms, floor_level, monthly_rent_estimate,
                listing_description, status, created_at
            ) VALUES (
                %(id)s, %(source_url)s, %(project_name)s, %(district)s, %(address)s,
                %(property_type)s, %(tenure)s, %(top_year)s, %(asking_price)s,
                %(floor_area_sqft)s, %(bedrooms)s, %(bathrooms)s, %(floor_level)s,
                %(monthly_rent_estimate)s, %(listing_description)s, %(status)s,
                %(created_at)s
            )
            """,
            values,
        )
    return property_id


def _update_missing_property_fields(
    conn,
    property_row: Dict[str, Any],
    identity: Dict[str, Any],
    fields: Dict[str, Any],
) -> List[str]:
    candidate_values = _non_empty_fields(identity, fields)
    updates = []
    params: List[Any] = []
    changed_fields = []

    for field, value in candidate_values.items():
        if field == "project_name":
            continue
        if property_row.get(field) in (None, ""):
            updates.append(f"{field} = %s")
            params.append(value)
            changed_fields.append(field)

    if not updates:
        return []

    params.append(property_row["id"])
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE properties
            SET {", ".join(updates)}
            WHERE id = %s
            """,
            params,
        )
    return changed_fields


def _current_property_values(
    conn,
    property_id: Optional[str],
    identity: Dict[str, Any],
    fields: Dict[str, Any],
) -> Dict[str, Any]:
    values = _non_empty_fields(identity, fields)
    if not property_id:
        return values

    row = fetch_one(conn, "SELECT * FROM properties WHERE id = %s", [property_id])
    if not row:
        return values

    merged = {field: row.get(field) for field in STRUCTURED_FIELDS}
    merged.update({field: value for field, value in values.items() if value not in (None, "")})
    return merged


def _missing_fields(values: Dict[str, Any]) -> List[str]:
    return [field for field in ANALYSIS_FIELDS if values.get(field) in (None, "")]


def _follow_up_questions(missing_fields: List[str]) -> List[str]:
    question_map = {
        "asking_price": "What is the asking price?",
        "floor_area_sqft": "What is the unit size in sqft?",
        "bedrooms": "How many bedrooms does the unit have?",
        "monthly_rent_estimate": "Do you have an estimated monthly rent?",
        "tenure": "Is the property freehold or leasehold?",
        "top_year": "What is the TOP or completion year?",
        "district": "Which district is the property in?",
    }
    return [question_map[field] for field in missing_fields if field in question_map][:4]


def _save_notes(
    conn,
    property_id: Optional[str],
    notes: List[Dict[str, str]],
    intake_event_id: str,
) -> List[Dict[str, str]]:
    if not property_id:
        return []

    saved_notes = []
    now = _now()
    with conn.cursor() as cursor:
        for note in notes:
            note_id = _new_id("note_user")
            cursor.execute(
                """
                INSERT INTO property_notes (
                    id, property_id, note_type, note_text, noted_at, source_intake_event_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    note_id,
                    property_id,
                    note["note_type"],
                    note["note_text"],
                    now,
                    intake_event_id,
                ],
            )
            saved_notes.append({"id": note_id, **note})
    return saved_notes


def _save_intake_event(
    conn,
    event_id: str,
    raw_input: str,
    property_id: Optional[str],
    extracted_fields: Dict[str, Any],
    extracted_notes: List[Dict[str, str]],
    missing_fields: List[str],
    follow_up_questions: List[str],
    confidence: float,
    status: str,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO intake_events (
                id, raw_input, property_id, extracted_fields, extracted_notes,
                missing_fields, follow_up_questions, confidence, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event_id,
                raw_input,
                property_id,
                Json(extracted_fields),
                Json(extracted_notes),
                Json(missing_fields),
                Json(follow_up_questions),
                confidence,
                status,
                _now(),
            ],
        )


def process_intake(conn, message: str) -> Dict[str, Any]:
    llm_extraction = _llm_extract(message)
    planner = "llm" if llm_extraction else "fallback"
    extraction = _normalize_extraction(llm_extraction or _fallback_extract(message), message)
    identity = extraction["property_identity"]
    fields = extraction["structured_fields"]
    notes = extraction["notes"]

    event_id = _new_id("intake")
    matched_property = _find_matching_property(conn, identity)
    changed_fields: List[str] = []
    created_property = False

    if matched_property:
        property_id = matched_property["id"]
        changed_fields = _update_missing_property_fields(conn, matched_property, identity, fields)
    else:
        property_id = _create_property_shell(conn, identity, fields)
        created_property = bool(property_id)

    current_values = _current_property_values(conn, property_id, identity, fields)
    missing_fields = _missing_fields(current_values)
    follow_up_questions = _follow_up_questions(missing_fields)

    if not property_id:
        status = "needs_identity"
        if "Which project or address is this note for?" not in follow_up_questions:
            follow_up_questions.insert(0, "Which project or address is this note for?")
    elif missing_fields:
        status = "needs_more_details"
    else:
        status = "ready_for_analysis"

    saved_notes = _save_notes(conn, property_id, notes, event_id)
    extracted_fields = {
        "property_identity": identity,
        "structured_fields": fields,
    }
    _save_intake_event(
        conn=conn,
        event_id=event_id,
        raw_input=message,
        property_id=property_id,
        extracted_fields=extracted_fields,
        extracted_notes=notes,
        missing_fields=missing_fields,
        follow_up_questions=follow_up_questions,
        confidence=extraction["confidence"],
        status=status,
    )
    conn.commit()

    return {
        "intake_event_id": event_id,
        "status": status,
        "planner": planner,
        "property_id": property_id,
        "created_property": created_property,
        "updated_fields": changed_fields,
        "extracted_fields": extracted_fields,
        "notes": notes,
        "saved_notes": saved_notes,
        "missing_fields": missing_fields,
        "follow_up_questions": follow_up_questions,
        "confidence": extraction["confidence"],
    }


def list_intake_events(conn, limit: int = 50) -> List[Dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT * FROM intake_events
        ORDER BY created_at DESC
        LIMIT %s
        """,
        [limit],
    )

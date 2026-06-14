from typing import Any, Dict, List, Optional

from app.services.property_service import list_notes


def get_notes_for_property(
    conn,
    property_id: str,
    note_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return list_notes(conn, property_id=property_id, note_type=note_type)

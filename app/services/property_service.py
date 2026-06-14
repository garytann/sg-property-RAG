from typing import Any, Dict, List, Optional

from app.db.database import fetch_all, fetch_one


def list_properties(
    conn,
    status: Optional[str] = None,
    district: Optional[int] = None,
    project_name: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []

    if status:
        clauses.append("status = %s")
        params.append(status)
    if district is not None:
        clauses.append("district = %s")
        params.append(district)
    if project_name:
        clauses.append("LOWER(project_name) LIKE LOWER(%s)")
        params.append(f"%{project_name}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return fetch_all(
        conn,
        f"""
        SELECT * FROM properties
        {where}
        ORDER BY project_name
        LIMIT %s
        """,
        params,
    )


def get_property(conn, property_id: str) -> Optional[Dict[str, Any]]:
    return fetch_one(conn, "SELECT * FROM properties WHERE id = %s", [property_id])


def find_properties_by_names(
    conn,
    names: List[str],
) -> List[Dict[str, Any]]:
    if not names:
        return []

    matches: Dict[str, Dict[str, Any]] = {}
    for name in names:
        rows = fetch_all(
            conn,
            """
            SELECT * FROM properties
            WHERE LOWER(project_name) LIKE LOWER(%s)
            ORDER BY project_name
            LIMIT 5
            """,
            [f"%{name.strip()}%"],
        )
        for row in rows:
            matches[row["id"]] = row

    return list(matches.values())


def list_notes(
    conn,
    property_id: Optional[str] = None,
    note_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []

    if property_id:
        clauses.append("property_id = %s")
        params.append(property_id)
    if note_type:
        clauses.append("note_type = %s")
        params.append(note_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return fetch_all(
        conn,
        f"""
        SELECT * FROM property_notes
        {where}
        ORDER BY noted_at, id
        LIMIT %s
        """,
        params,
    )

from typing import Any, Dict, Iterable, List, Mapping, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import DATABASE_URL, STORAGE_DIR


def get_connection():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def initialize_database(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                source_url TEXT,
                project_name TEXT NOT NULL,
                district INTEGER,
                address TEXT,
                property_type TEXT,
                tenure TEXT,
                top_year INTEGER,
                asking_price DOUBLE PRECISION,
                floor_area_sqft DOUBLE PRECISION,
                bedrooms INTEGER,
                bathrooms INTEGER,
                floor_level TEXT,
                monthly_rent_estimate DOUBLE PRECISION,
                listing_description TEXT,
                status TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS property_notes (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                note_type TEXT NOT NULL,
                note_text TEXT NOT NULL,
                noted_at TEXT,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_properties_project_name
                ON properties(project_name);
            CREATE INDEX IF NOT EXISTS idx_properties_status
                ON properties(status);
            CREATE INDEX IF NOT EXISTS idx_properties_district
                ON properties(district);
            CREATE INDEX IF NOT EXISTS idx_notes_property_id
                ON property_notes(property_id);
            CREATE INDEX IF NOT EXISTS idx_notes_type
                ON property_notes(note_type);
            """
        )
    conn.commit()


def row_to_dict(row: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(row)


def rows_to_dicts(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def fetch_one(
    conn,
    query: str,
    params: Optional[Iterable[Any]] = None,
) -> Optional[Dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params or []))
        row = cursor.fetchone()
    return row_to_dict(row) if row else None


def fetch_all(
    conn,
    query: str,
    params: Optional[Iterable[Any]] = None,
) -> List[Dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params or []))
        rows = cursor.fetchall()
    return rows_to_dicts(rows)

import csv
from pathlib import Path
from typing import Any, Dict, Iterable

from app.config import PROPERTIES_CSV, PROPERTY_NOTES_CSV
from app.db.database import get_connection, initialize_database


INTEGER_FIELDS = {"district", "top_year", "bedrooms", "bathrooms"}
FLOAT_FIELDS = {"asking_price", "floor_area_sqft", "monthly_rent_estimate"}


def _coerce_value(field: str, value: str) -> Any:
    if value == "":
        return None
    if field in INTEGER_FIELDS:
        return int(value)
    if field in FLOAT_FIELDS:
        return float(value)
    return value


def _read_csv(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {field: _coerce_value(field, value) for field, value in row.items()}


def seed_database(
    properties_csv: Path = PROPERTIES_CSV,
    notes_csv: Path = PROPERTY_NOTES_CSV,
) -> Dict[str, int]:
    with get_connection() as conn:
        initialize_database(conn)
        properties = list(_read_csv(properties_csv))
        notes = list(_read_csv(notes_csv))

        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM property_notes")
            cursor.execute("DELETE FROM properties")

            cursor.executemany(
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
                properties,
            )

            cursor.executemany(
                """
                INSERT INTO property_notes (
                    id, property_id, note_type, note_text, noted_at
                ) VALUES (
                    %(id)s, %(property_id)s, %(note_type)s, %(note_text)s, %(noted_at)s
                )
                """,
                notes,
            )
        conn.commit()

    return {"properties": len(properties), "property_notes": len(notes)}

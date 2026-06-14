import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/property_ai_poc",
)
VECTOR_INDEX_PATH = STORAGE_DIR / "rag_index.json"

PROPERTIES_CSV = DATA_DIR / "sample_properties.csv"
PROPERTY_NOTES_CSV = DATA_DIR / "sample_property_notes.csv"

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
ENV_PATH = BASE_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


_load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/property_ai_poc",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
VECTOR_INDEX_PATH = STORAGE_DIR / "rag_index.json"

PROPERTIES_CSV = DATA_DIR / "sample_properties.csv"
PROPERTY_NOTES_CSV = DATA_DIR / "sample_property_notes.csv"

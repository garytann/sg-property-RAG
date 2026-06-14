import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.database import get_connection, initialize_database
from app.rag.vector_store import rebuild_index


if __name__ == "__main__":
    with get_connection() as conn:
        initialize_database(conn)
        counts = rebuild_index(conn)
    print(f"Indexed {counts['documents']} documents with {counts['terms']} terms.")

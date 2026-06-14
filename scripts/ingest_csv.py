import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed_database


if __name__ == "__main__":
    counts = seed_database()
    print(f"Loaded {counts['properties']} properties and {counts['property_notes']} notes.")

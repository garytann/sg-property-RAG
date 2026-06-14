import json
from typing import Any, Dict, List, Optional

from app.config import VECTOR_INDEX_PATH
from app.db.database import fetch_all
from app.rag.embed import build_idf, cosine_similarity, tfidf_vector, vector_norm


def _property_doc(property_row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"listing_{property_row['id']}",
        "property_id": property_row["id"],
        "project_name": property_row["project_name"],
        "document_type": "listing_description",
        "text": property_row.get("listing_description") or "",
        "source": "properties.listing_description",
    }


def _note_doc(note_row: Dict[str, Any], project_name: str) -> Dict[str, Any]:
    return {
        "id": note_row["id"],
        "property_id": note_row["property_id"],
        "project_name": project_name,
        "document_type": note_row["note_type"],
        "text": note_row["note_text"],
        "source": "property_notes.note_text",
    }


def load_documents_from_database(conn) -> List[Dict[str, Any]]:
    properties = fetch_all(conn, "SELECT * FROM properties ORDER BY id")
    property_names = {row["id"]: row["project_name"] for row in properties}

    docs = [_property_doc(row) for row in properties if row["listing_description"]]

    notes = fetch_all(conn, "SELECT * FROM property_notes ORDER BY id")
    docs.extend(
        _note_doc(row, property_names.get(row["property_id"], "Unknown project"))
        for row in notes
    )
    return docs


def rebuild_index(conn) -> Dict[str, int]:
    docs = load_documents_from_database(conn)
    idf = build_idf(doc["text"] for doc in docs)

    indexed_docs = []
    for doc in docs:
        vector = tfidf_vector(doc["text"], idf)
        indexed_docs.append(
            {
                **doc,
                "vector": vector,
                "norm": vector_norm(vector),
            }
        )

    VECTOR_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    VECTOR_INDEX_PATH.write_text(
        json.dumps({"idf": idf, "documents": indexed_docs}, indent=2),
        encoding="utf-8",
    )
    return {"documents": len(indexed_docs), "terms": len(idf)}


def load_index() -> Dict[str, Any]:
    if not VECTOR_INDEX_PATH.exists():
        raise FileNotFoundError(
            f"Vector index not found at {VECTOR_INDEX_PATH}. Run scripts/rebuild_vector_index.py first."
        )
    return json.loads(VECTOR_INDEX_PATH.read_text(encoding="utf-8"))


def search_index(
    query: str,
    top_k: int = 8,
    property_id: Optional[str] = None,
    document_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    index = load_index()
    query_vector = tfidf_vector(query, index["idf"])
    query_norm = vector_norm(query_vector)

    scored_docs = []
    for doc in index["documents"]:
        if property_id and doc["property_id"] != property_id:
            continue
        if document_type and doc["document_type"] != document_type:
            continue

        score = cosine_similarity(
            query_vector,
            query_norm,
            doc["vector"],
            doc["norm"],
        )
        if score > 0:
            clean_doc = {
                key: value
                for key, value in doc.items()
                if key not in {"vector", "norm"}
            }
            clean_doc["score"] = round(score, 4)
            scored_docs.append(clean_doc)

    scored_docs.sort(key=lambda item: item["score"], reverse=True)
    return scored_docs[:top_k]

from typing import Any, Dict, List, Optional

from app.rag.vector_store import search_index


def retrieve_context(
    query: str,
    top_k: int = 8,
    property_id: Optional[str] = None,
    document_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return search_index(
        query=query,
        top_k=top_k,
        property_id=property_id,
        document_type=document_type,
    )


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


def retrieve_context_with_plan(
    plan: Dict[str, Any],
    top_k: int = 12,
    property_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    queries = plan.get("search_queries") or []
    if not queries:
        return []

    filters = plan.get("filters") or {}
    document_type = filters.get("document_type")
    per_query_top_k = max(4, min(top_k, top_k // len(queries) + 3))

    docs_by_id: Dict[str, Dict[str, Any]] = {}
    for query in queries:
        for doc in search_index(
            query=query,
            top_k=per_query_top_k,
            property_id=property_id,
            document_type=document_type,
        ):
            doc_id = doc["id"]
            existing = docs_by_id.get(doc_id)
            if not existing or doc["score"] > existing["score"]:
                docs_by_id[doc_id] = {
                    **doc,
                    "matched_queries": [query],
                }
            elif query not in existing["matched_queries"]:
                existing["matched_queries"].append(query)

    reranked_docs = list(docs_by_id.values())
    reranked_docs.sort(
        key=lambda doc: (doc["score"], len(doc["matched_queries"])),
        reverse=True,
    )
    return reranked_docs[:top_k]

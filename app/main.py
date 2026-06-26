from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.database import fetch_one, get_connection, initialize_database
from app.db.seed import seed_database
from app.rag.retrieval import retrieve_context
from app.rag.vector_store import rebuild_index
from app.services.chat_service import answer_chat
from app.services.intake_service import list_intake_events, process_intake
from app.services.property_service import get_property, list_notes, list_properties
from app.tools.calculations import (
    calculate_buyer_stamp_duty,
    calculate_gross_yield,
    calculate_psf,
    estimate_monthly_mortgage,
)


app = FastAPI(
    title="Property AI POC Backend",
    description="Lightweight property-analysis backend with Postgres, RAG search, calculation tools, and chat orchestration.",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    top_k: int = Field(default=12, ge=1, le=30)


class SearchNotesRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=30)
    property_id: Optional[str] = None
    document_type: Optional[str] = None


class IntakeRequest(BaseModel):
    message: str = Field(..., min_length=1)


class YieldRequest(BaseModel):
    price: float = Field(..., gt=0)
    monthly_rent: float = Field(..., ge=0)


class PsfRequest(BaseModel):
    price: float = Field(..., gt=0)
    floor_area_sqft: float = Field(..., gt=0)


class BsdRequest(BaseModel):
    price: float = Field(..., gt=0)


class MortgageRequest(BaseModel):
    principal: float = Field(..., gt=0)
    annual_interest_rate: float = Field(..., ge=0)
    tenure_years: int = Field(..., gt=0, le=50)


def _ensure_loaded() -> None:
    with get_connection() as conn:
        initialize_database(conn)
        property_count = fetch_one(conn, "SELECT COUNT(*) AS count FROM properties")
        if not property_count or property_count["count"] == 0:
            seed_database()
        rebuild_index(conn)


@app.on_event("startup")
def startup_event() -> None:
    _ensure_loaded()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/admin/ingest")
def ingest() -> dict:
    counts = seed_database()
    with get_connection() as conn:
        index_counts = rebuild_index(conn)
    return {"loaded": counts, "index": index_counts}


@app.post("/admin/rebuild-index")
def rebuild_rag_index() -> dict:
    with get_connection() as conn:
        return rebuild_index(conn)


@app.get("/properties")
def get_properties(
    status: Optional[str] = None,
    district: Optional[int] = None,
    project_name: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list:
    with get_connection() as conn:
        return list_properties(
            conn,
            status=status,
            district=district,
            project_name=project_name,
            limit=limit,
        )


@app.get("/properties/{property_id}")
def get_property_by_id(property_id: str) -> dict:
    with get_connection() as conn:
        property_row = get_property(conn, property_id)
        if not property_row:
            raise HTTPException(status_code=404, detail="Property not found")
        return property_row


@app.get("/properties/{property_id}/notes")
def get_property_notes(
    property_id: str,
    note_type: Optional[str] = None,
) -> list:
    with get_connection() as conn:
        if not get_property(conn, property_id):
            raise HTTPException(status_code=404, detail="Property not found")
        return list_notes(conn, property_id=property_id, note_type=note_type)


@app.post("/search-notes")
def search_notes(request: SearchNotesRequest) -> list:
    return retrieve_context(
        query=request.query,
        top_k=request.top_k,
        property_id=request.property_id,
        document_type=request.document_type,
    )


@app.post("/intake")
def intake(request: IntakeRequest) -> dict:
    with get_connection() as conn:
        result = process_intake(conn, request.message)
        index_counts = rebuild_index(conn)
        return {**result, "index": index_counts}


@app.get("/intake-events")
def get_intake_events(limit: int = Query(default=50, ge=1, le=200)) -> list:
    with get_connection() as conn:
        return list_intake_events(conn, limit=limit)


@app.post("/calculate/yield")
def calculate_yield(request: YieldRequest) -> dict:
    return calculate_gross_yield(request.price, request.monthly_rent)


@app.post("/calculate/psf")
def calculate_price_psf(request: PsfRequest) -> dict:
    return calculate_psf(request.price, request.floor_area_sqft)


@app.post("/calculate/bsd")
def calculate_bsd(request: BsdRequest) -> dict:
    return calculate_buyer_stamp_duty(request.price)


@app.post("/calculate/mortgage")
def calculate_mortgage(request: MortgageRequest) -> dict:
    return estimate_monthly_mortgage(
        principal=request.principal,
        annual_interest_rate=request.annual_interest_rate,
        tenure_years=request.tenure_years,
    )


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    with get_connection() as conn:
        return answer_chat(conn, request.message, top_k=request.top_k)

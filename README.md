# Property AI POC Backend

Lightweight FastAPI backend for experimenting with a property-search second brain:

- Postgres stores structured property rows and notes.
- A local TF-IDF index provides first-pass RAG over notes and listing descriptions.
- Calculation tools compute PSF, gross rental yield, illustrative BSD, and mortgage estimates.
- A `/chat` endpoint retrieves context, runs tools, and returns a source-backed analyst response.

## Postgres Setup

The app reads `DATABASE_URL`. If it is not set, it uses:

```text
postgresql://localhost:5432/property_ai_poc
```

Create the database first using your Postgres GUI, or with `createdb`:

```bash
createdb property_ai_poc
```

If your Postgres requires a username/password, set `DATABASE_URL` before running scripts:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/property_ai_poc"
```

## Run Locally

```bash
conda activate property-ai-poc
python scripts/ingest_csv.py
python scripts/rebuild_vector_index.py
uvicorn app.main:app --port 8000
```

Then open:

```text
http://127.0.0.1:8000/docs
```

If you prefer not to activate the env:

```bash
conda run -n property-ai-poc python scripts/ingest_csv.py
conda run -n property-ai-poc python scripts/rebuild_vector_index.py
conda run -n property-ai-poc uvicorn app.main:app --port 8000
```

## Useful Endpoints

```text
GET  /properties
GET  /properties/{property_id}
GET  /properties/{property_id}/notes
POST /search-notes
POST /calculate/yield
POST /calculate/psf
POST /calculate/bsd
POST /calculate/mortgage
POST /chat
```

Example chat request:

```json
{
  "message": "Which shortlisted property has the best rental yield but worrying risk notes?",
  "top_k": 12
}
```

## Data

The sample data lives in `data/sample_properties.csv` and `data/sample_property_notes.csv`.
The generated RAG index lives under `storage/`. The structured property data lives in Postgres.

The current RAG implementation is intentionally dependency-light. Replace `app/rag/vector_store.py`
with OpenAI embeddings, Chroma, FAISS, or pgvector when you are ready to learn production-style retrieval.

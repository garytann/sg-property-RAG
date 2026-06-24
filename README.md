# Property AI POC Backend

Lightweight FastAPI backend for experimenting with a property-search second brain:

- Postgres stores structured property rows and notes.
- A local TF-IDF index provides first-pass RAG over notes and listing descriptions.
- An optional LLM retrieval planner rewrites vague chat questions into better index searches.
- Calculation tools compute PSF, gross rental yield, illustrative BSD, and mortgage estimates.
- A `/chat` endpoint retrieves context, runs tools, and returns a source-backed analyst response.

## Postgres Setup

The app reads local settings from `.env`. Start from the example file:

```bash
cp .env.example .env
```

If `DATABASE_URL` is not set in `.env` or your shell, the app uses:

```text
postgresql://localhost:5432/property_ai_poc
```

Create the database first using your Postgres GUI, or with `createdb`:

```bash
createdb property_ai_poc
```

If your Postgres requires a username/password, set `DATABASE_URL` before running scripts:

```text
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/property_ai_poc
```

## Optional LLM Retrieval Planner

The `/chat` endpoint can use an LLM to rewrite a user question into 2-4 focused RAG search queries before searching `storage/rag_index.json`.

Set an OpenAI API key to enable it:

```text
OPENAI_API_KEY=your_api_key_here
```

The model is configurable:

```text
OPENAI_MODEL=gpt-5.5
```

If `OPENAI_API_KEY` is not set, the app still works. It uses a deterministic local fallback planner with keyword expansion for risk, rental yield, location, and viewing/layout questions.

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

The chat response includes a `retrieval_plan` field showing whether the planner used `llm` or `fallback`, the expanded search queries, and any filters it applied.

## Data

The sample data lives in `data/sample_properties.csv` and `data/sample_property_notes.csv`.
The generated RAG index lives under `storage/`. The structured property data lives in Postgres.

The current RAG implementation is intentionally dependency-light. Replace `app/rag/vector_store.py`
with OpenAI embeddings, Chroma, FAISS, or pgvector when you are ready to learn production-style retrieval.

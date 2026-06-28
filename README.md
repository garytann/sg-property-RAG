# Property AI POC Backend

Lightweight FastAPI backend for experimenting with a property-search second brain:

- Postgres stores structured property rows and notes.
- A local TF-IDF index provides first-pass RAG over notes and listing descriptions.
- An optional LLM retrieval planner rewrites vague chat questions into better index searches.
- Calculation tools compute PSF, gross rental yield, illustrative BSD, and mortgage estimates.
- A `/chat` endpoint retrieves context, runs tools, and returns a source-backed analyst response.


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

## Run With Docker

Create your local environment file:

```bash
cp .env.example .env
```

For the Docker stack, keep the Postgres host as the Compose service name:

```text
POSTGRES_HOST=postgres
POSTGRES_DB=property_ai_poc
POSTGRES_USER=property_user
POSTGRES_PASSWORD=property_password
NGINX_HTTP_PORT=80
```

Start the full stack:

```bash
docker compose up --build
```

Open the application through Nginx:

```text
http://localhost
```

Nginx routes traffic like this:

```text
Browser
  |
  v
Nginx :80
  |-- /      -> React frontend container
  |-- /api/* -> FastAPI backend container
  |-- /docs  -> FastAPI docs
```

The Docker services are:

```text
postgres  Postgres database with a named volume
api       FastAPI backend on internal port 8000
frontend  Built React static app on internal port 8080
nginx     Public gateway on port 80
```

To stop the stack:

```bash
docker compose down
```

To remove the database volume as well:

```bash
docker compose down -v
```


## Useful Endpoints

```text
GET  /properties
GET  /properties/{property_id}
GET  /properties/{property_id}/notes
POST /intake
GET  /intake-events
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

## Intake Flow

The `/intake` endpoint accepts messy user input and separates it into canonical property fields, notes, missing fields, and follow-up questions.

Example request:

```json
{
  "message": "Viewed Grand Dunman. Nice layout, but road noise was obvious. Agent said asking is around 1.6M."
}
```

Backend flow for incomplete information:

```text
User input
   |
   v
POST /intake
   |
   v
+--------------------------+
| Preserve raw input       |
| intake_events.raw_input  |
+--------------------------+
   |
   v
+--------------------------+
| Extract meaning          |
| - project identity       |
| - structured fields      |
| - viewing/risk/rent notes|
| - confidence             |
+--------------------------+
   |
   v
+--------------------------+
| Enough identity?         |
| project/address/source?  |
+--------------------------+
   | yes                         | no
   v                             v
+--------------------------+   +--------------------------+
| Find existing property   |   | Save intake_event only   |
| or create property shell |   | status: needs_identity   |
+--------------------------+   +--------------------------+
   |                             |
   v                             v
+--------------------------+   +--------------------------+
| Fill only empty fields   |   | Ask: which project or    |
| never invent/overwrite   |   | address is this for?     |
+--------------------------+   +--------------------------+
   |
   v
+--------------------------+
| Save notes if property   |
| is known                 |
| property_notes           |
+--------------------------+
   |
   v
+--------------------------+
| Check missing analysis   |
| fields: price, sqft,     |
| beds, rent, tenure, TOP, |
| district                 |
+--------------------------+
   |
   v
+--------------------------+
| Save intake_event        |
| - extracted JSON         |
| - missing fields         |
| - follow-up questions    |
| - status                 |
+--------------------------+
   |
   v
+--------------------------+
| Rebuild local RAG index  |
| so new notes are         |
| searchable by /chat      |
+--------------------------+
   |
   v
Response to user:
- created/updated property id
- extracted fields
- saved notes
- missing fields
- next follow-up questions
```

This design lets the app capture partial truth without forcing incomplete user input into a fully populated structured listing.

## Data

The sample data lives in `data/sample_properties.csv` and `data/sample_property_notes.csv`.
The generated RAG index lives under `storage/`. The structured property data lives in Postgres.

The current RAG implementation is intentionally dependency-light. Replace `app/rag/vector_store.py`
with OpenAI embeddings, Chroma, FAISS, or pgvector when you are ready to learn production-style retrieval.

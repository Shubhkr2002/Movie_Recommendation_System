# Movie Recommendation API — Backend

A production-quality FastAPI backend for the existing Movie Recommendation
System. It does **not** change the recommendation algorithm — it wraps the
existing TF-IDF cosine-similarity logic and TMDB integration (originally in
a single `main.py`) in a clean, modular, testable service architecture, and
serves the same Streamlit frontend (`app.py`) that's already deployed.

> **Note on scope:** this backend is built around the *actual* dataset
> already in this project — `df.pkl`, `indices.pkl`, `tfidf.pkl`, and
> `tfidf_matrix.pkl` (a TF-IDF + cosine-similarity content recommender), and
> exposes the endpoints the deployed frontend already calls (`/home`,
> `/tmdb/search`, `/movie/id/{id}`, `/recommend/genre`, `/recommend/tfidf`,
> `/movie/search`), plus `/` and `/health`. It intentionally does not add a
> `movie_list.pkl` / `similarity.pkl` / simple `/movies` + `/recommend`
> pair, since those files don't exist in this project — that would be a
> different dataset, not this one.

---

## 1. Project Overview

- **Frontend:** Streamlit (`app.py`), already deployed on Render, calls this
  API over REST.
- **Backend:** FastAPI, this repo. Fully decoupled from the frontend.
- **Recommendation approach:**
  - **Content-based (local):** TF-IDF vectors over movie metadata (`df.pkl`
    / `tfidf.pkl` / `tfidf_matrix.pkl`), ranked by cosine similarity
    (`indices.pkl` maps titles → matrix rows).
  - **Genre-based (TMDB):** given a movie's first genre, discover other
    popular movies in that genre via the TMDB `/discover/movie` endpoint.
- **Posters/metadata:** fetched live from TMDB, never stored locally.

## 2. Architecture

```
Streamlit frontend (app.py, deployed separately)
        │  REST (JSON over HTTPS)
        ▼
FastAPI backend (this repo)
 ├── api/          → routes + dependency injection
 ├── services/      → RecommendationService (TF-IDF), TMDBService (HTTP client)
 ├── schemas/       → Pydantic request/response models
 ├── core/          → settings, logging, security helpers
 ├── middleware/    → request logging
 └── utils/         → global exception handlers
        │
        ▼
data/ (df.pkl, indices.pkl, tfidf.pkl, tfidf_matrix.pkl)  — loaded once at startup
```

Design principles applied:
- **Singleton services, loaded once.** `RecommendationService` loads all
  four pickles exactly once at startup (`app.state`), never per-request.
  `TMDBService` reuses a single `httpx.AsyncClient` connection pool for the
  life of the process.
- **Dependency injection.** Routes receive services via `Depends(...)`
  (`app/api/dependencies.py`), never via module-level globals — this makes
  every route trivially testable with fakes (see `tests/test_home.py`).
- **Separation of concerns.** Routes only orchestrate; all TF-IDF math
  lives in `RecommendationService`, all TMDB HTTP logic lives in
  `TMDBService`.
- **Consistent error shape.** Every error (404, 422, 500, 502, 503) returns
  `{"error": "<code>", "detail": "<message>"}` via global exception
  handlers, never a raw stack trace.

## 3. Folder Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── routes.py            # all endpoints
│   │   └── dependencies.py      # DI providers for services/settings
│   ├── services/
│   │   ├── recommendation_service.py  # TF-IDF load + cosine similarity
│   │   └── tmdb_service.py            # TMDB HTTP client
│   ├── schemas/
│   │   ├── request.py           # validated request shapes
│   │   └── response.py          # response models (ported from main.py)
│   ├── models/                  # reserved for future ORM/domain models
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── logging.py           # logging setup
│   │   └── security.py          # input-validation helpers
│   ├── utils/
│   │   └── exception_handlers.py
│   ├── middleware/
│   │   └── logging_middleware.py
│   └── main.py                  # app factory, lifespan, wiring
├── data/
│   ├── df.pkl
│   ├── indices.pkl
│   ├── tfidf.pkl
│   └── tfidf_matrix.pkl
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_home.py
│   └── test_recommendations.py
├── requirements.txt
├── runtime.txt
├── .env.example
├── Dockerfile
├── .dockerignore
├── render.yaml
└── README.md
```

## 4. API Endpoints

| Method | Path                  | Description                                            |
|--------|------------------------|----------------------------------------------------------|
| GET    | `/`                    | API name + version                                      |
| GET    | `/health`               | Readiness check (503 until the dataset finishes loading) |
| GET    | `/home`                 | TMDB home feed (`trending`, `popular`, `top_rated`, `upcoming`, `now_playing`) |
| GET    | `/tmdb/search`           | Raw TMDB keyword search                                  |
| GET    | `/movie/id/{tmdb_id}`     | Full movie details from TMDB                             |
| GET    | `/recommend/genre`        | TMDB genre-based recommendations                          |
| GET    | `/recommend/tfidf`        | Local TF-IDF recommendations (debug/utility, no posters)   |
| GET    | `/movie/search`           | Bundle: details + TF-IDF recs (with posters) + genre recs |
| GET    | `/docs`                  | Swagger UI (auto-generated)                              |
| GET    | `/redoc`                 | ReDoc UI (auto-generated)                                 |

### Example: `GET /recommend/tfidf?title=Toy Story&top_n=3`

```json
[
  {"title": "Toy Story 2", "score": 0.395},
  {"title": "Toy Story 3", "score": 0.377},
  {"title": "Small Fry", "score": 0.254}
]
```

### Example: `GET /movie/search?query=Avatar`

```json
{
  "query": "Avatar",
  "movie_details": {
    "tmdb_id": 19995,
    "title": "Avatar",
    "overview": "...",
    "release_date": "2009-12-10",
    "poster_url": "https://image.tmdb.org/t/p/w500/....jpg",
    "backdrop_url": "https://image.tmdb.org/t/p/w500/....jpg",
    "genres": [{"id": 28, "name": "Action"}]
  },
  "tfidf_recommendations": [
    {"title": "Aliens", "score": 0.31, "tmdb": {"tmdb_id": 679, "title": "Aliens", "poster_url": "...", "release_date": "1986-07-18", "vote_average": 7.9}}
  ],
  "genre_recommendations": [
    {"tmdb_id": 24428, "title": "The Avengers", "poster_url": "...", "release_date": "2012-04-25", "vote_average": 7.7}
  ]
}
```

### Error shape (all errors)

```json
{"error": "not_found", "detail": "Title not found in local dataset: 'xyz'"}
```

## 5. Environment Variables

See `.env.example` for the full list. The only **required** variable is:

| Variable        | Required | Description                          |
|-----------------|----------|-----------------------------------------|
| `TMDB_API_KEY`   | Yes      | Your TMDB v3 API key                    |
| `APP_NAME`       | No       | Defaults to "Movie Recommendation API"  |
| `API_VERSION`    | No       | Defaults to "1.0"                       |
| `DEBUG`          | No       | Defaults to `false`                     |
| `LOG_LEVEL`      | No       | Defaults to `INFO`                      |
| `ALLOWED_ORIGINS`| No       | JSON array, defaults to `["*"]`         |
| `ALLOWED_HOSTS`  | No       | JSON array, defaults to `["*"]`         |

## 6. Installation & Running Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and set your real TMDB_API_KEY

uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for interactive Swagger docs.

## 7. Running with Docker

```bash
cd backend
docker build -t movie-recommendation-backend .
docker run --env-file .env -p 8000:8000 movie-recommendation-backend
```

## 8. Deploying on Render

This repo includes `render.yaml`, so Render can deploy it directly as a
Blueprint:

1. Push this `backend/` folder to a Git repository.
2. In Render: **New → Blueprint**, point it at the repo.
3. Render reads `render.yaml` and creates the web service automatically.
4. In the Render dashboard, set the `TMDB_API_KEY` env var (it's marked
   `sync: false` in `render.yaml` so it's never committed to Git).
5. Render runs `pip install -r requirements.txt` then starts the service
   with Gunicorn + Uvicorn workers, and polls `GET /health` to confirm the
   instance is ready before routing traffic to it.

No Dockerfile changes are needed if you'd rather deploy the Docker image
directly instead of Render's native Python runtime — both are included and
kept in sync.

## 9. Testing

```bash
cd backend
pytest tests/ -v
```

- `test_health.py` — root + health checks
- `test_recommendations.py` — the real TF-IDF algorithm against the real
  dataset (no mocking — this validates the actual recommendation math)
- `test_home.py` — TMDB-backed endpoints, using a fake `TMDBService` via
  FastAPI's `dependency_overrides` so tests run without network access or
  a real API key

All 8 tests pass against the real dataset shipped in `data/`.

## 10. Performance & Security Notes

- Pickle files are loaded **exactly once**, at process startup, and cached
  on `app.state` — never re-read from disk per-request.
- A single `httpx.AsyncClient` is reused for all TMDB calls (no per-request
  TLS handshakes).
- GZip middleware compresses large JSON responses (movie lists).
- No API keys are hardcoded anywhere; everything comes from environment
  variables via Pydantic Settings.
- Every input is validated by Pydantic/FastAPI's `Query(...)` constraints
  before it reaches the recommendation engine or TMDB.

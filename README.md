# Grocify

A New Zealand grocery price comparison app. Search products across Countdown, PAK'nSAVE, and New World, compare prices at nearby stores, and build a shopping trolley to find the cheapest option.

## Features

- **Product search** — full-text search with filters for chain, category, price range, and promotions
- **Location-aware** — uses geolocation to find nearby stores and show local pricing
- **Store map** — interactive map with clustering, powered by MapLibre GL
- **Trolley comparison** — build a shopping list, compare total cost across nearby stores, and get suggestions for unavailable items
- **Store rankings** — see which stores are cheapest by category

## Tech stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, MapLibre GL |
| Backend | FastAPI, SQLAlchemy 2 (async), Pydantic v2, Uvicorn |
| Database | PostgreSQL 15 + PostGIS |
| Cache | Redis 7 |
| Scrapers | HTTPX, Playwright |
| Infra | Docker Compose, Nginx |

## Project structure

```
api/                  # FastAPI backend
  app/
    routes/           # Endpoint handlers (products, stores, trolley, auth)
    services/         # Business logic (search, trolley, matching, rankings)
    scrapers/         # Product price scrapers per chain
    store_scrapers/   # Store location scrapers
    db/               # SQLAlchemy models, sessions, migrations
    schemas/          # Pydantic request/response models
    tests/            # Pytest suite

web/                  # React frontend
  src/
    pages/            # Landing, Explore, Trolley
    components/       # UI components (products, stores, filters, layout)
    hooks/            # Data fetching and state hooks
    contexts/         # Location and Trolley context providers
    lib/              # Utilities, formatters, theme config

infra/                # Docker, Nginx, Dockerfiles
```

## Getting started

### Prerequisites

- Docker & Docker Compose

### Run with Docker

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up
```

The API will be available at `http://localhost:8000` and the frontend at `http://localhost:5173`.

### Run manually

**Backend:**

```bash
cd api
poetry install
poetry run uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd web
npm install
npm run dev
```

Requires a running PostgreSQL (with PostGIS) and Redis instance. Set connection strings in `.env`:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/grocify
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<random-32-char-string>
```

### Run tests

```bash
cd api
python3 -m pytest app/tests/
```

## API overview

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/products` | Search products (filters, pagination, location) |
| GET | `/products/{id}` | Product detail with all store prices |
| GET | `/stores` | Nearby stores by lat/lon/radius |
| GET | `/stores/rankings` | Rank stores by category |
| POST | `/trolley/compare` | Compare cart cost across stores |
| POST | `/trolley/suggestions` | Suggest alternatives for missing items |
| GET | `/healthz` | Liveness probe |

## Supported chains

- **Countdown** (Woolworths NZ) — API-based product scraping, per-store pricing
- **PAK'nSAVE** (Foodstuffs) — Foodstuffs API integration
- **New World** (Foodstuffs) — Foodstuffs API integration

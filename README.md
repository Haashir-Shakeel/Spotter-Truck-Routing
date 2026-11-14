# Spotter Route Planner

Weather-aware truck routing. Enter an origin, destination, departure time and load weight, and the
app compares up to three routes by the wind, rain and snow the truck is expected to hit at each
checkpoint, then recommends the safest one. A heatmap with a 0-48 h slider shows the weather
around the whole trip.

- Live app: https://spotter-truck-routing-eight.vercel.app
- API health: https://spotter-api-q78i.onrender.com/api/v1/health/
- Walkthrough: _Loom link_

The API is on Render's free plan and sleeps when idle, so the first load can take up to a minute
("Waking API..." in the header).

## Stack

- Backend: Python 3.11, Django 5.2, Django REST Framework, PostgreSQL (SQLite locally)
- Frontend: React 19, TypeScript, Vite, Tailwind CSS, MapLibre GL
- Data: Mapbox (routes, geocoding), Open-Meteo (hourly forecasts)
- Hosting: Vercel (frontend), Render (API, Docker), Neon (Postgres)

## Running locally

You need a Mapbox access token (free). It is only used by the backend.

```bash
cp backend/.env.example backend/.env   # set MAPBOX_ACCESS_TOKEN
docker compose up --build
```

Frontend at http://localhost:5173, API at http://localhost:8000.

Without Docker:

```bash
cd backend
cp .env.example .env        # set MAPBOX_ACCESS_TOKEN
uv sync
uv run python manage.py migrate
uv run python manage.py runserver

cd frontend                 # in another terminal, Node 24
npm install
npm run dev
```

Tests and lint:

```bash
cd backend && uv run pytest && uv run ruff check .
cd frontend && npm test && npm run lint && npm run typecheck
```

## How a route is scored

1. Up to three distinct routes from Mapbox. When it returns fewer (it usually gives two for US
   trips), an extra real route is requested through a waypoint beside the midpoint. It is kept
   only if it is a different road and at most 30% slower, and it is tagged "Via waypoint".
2. Checkpoints every 10, 25 or 50 miles, each with an estimated arrival time.
3. Each checkpoint gets the forecast for the hour the truck arrives and is classified with the
   assessment's wind/rain/snow table and load rules. Its risk is the worst of the three.
4. Routes with any No Travel miles are excluded. The rest are ranked by fewest Severe miles, then
   High miles, then lowest average risk, then shortest time.

## Decisions and assumptions

- The brief's ranges share endpoints (rain 0.10-0.25 and 0.25-0.50). I used half-open intervals
  and kept the explicit `>` thresholds for No Travel.
- Wind is interpolated between forecast hours. Rain and snow are hourly totals, so they use the
  hour containing the arrival time and are never interpolated.
- A segment between two checkpoints takes the higher of its two risks, which is conservative.
- Missing forecasts, or arrivals beyond the forecast range, are shown as Unavailable, never Low.
  If no route is safe, the result says so instead of recommending one.
- Times are shown in the origin's and destination's local time zones.
- The heatmap shows one forecast hour for the whole area, which is a different question from the
  route colours (weather at the truck's arrival). Both are labelled.
- "Demo weather" swaps only the weather input for clearly labelled synthetic storms, so every risk
  level can be shown on a calm day. Routing, scoring and ranking are unchanged.

## Limitations

- Mapbox's driving profile is not truck-aware (no height or weight restrictions). Load weight only
  affects the weather rules.
- Wind is sustained wind, not gusts.
- Free hosting: cold starts, and rate limits are kept in memory per worker.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/v1/trips/analyze/` | Analyze a trip |
| GET | `/api/v1/trips/{id}/` | Saved analysis |
| GET | `/api/v1/trips/{id}/corridor-forecast/` | Heatmap data, 49 hourly slices |
| GET | `/api/v1/places/?q=` | Place suggestions |
| GET | `/api/v1/health/` | Health check |

## Deployment

The API image is `backend/Dockerfile`; `start.sh` runs migrations and then gunicorn. Production
settings (`config.settings.prod`) need `DJANGO_SECRET_KEY`, `DATABASE_URL`, `MAPBOX_ACCESS_TOKEN`
and `CORS_ALLOWED_ORIGINS`, and will not start without the secret key and token. The frontend
needs `VITE_API_BASE_URL` at build time.

## Credits

Routing and geocoding by Mapbox. Weather data by [Open-Meteo.com](https://open-meteo.com/)
(CC BY 4.0). Basemap by OpenFreeMap, OpenMapTiles and OpenStreetMap contributors.

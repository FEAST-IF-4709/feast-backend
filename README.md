# FEAST Backend

Multi-tenant F&B SaaS backend built with Django 6, Django Channels, and PostgreSQL.

## Prerequisites

- Python 3.12
- PostgreSQL 15
- Redis 7

---

## Local dev setup

```bash
# 1. Clone and install dependencies
git clone <repo-url> && cd feast-backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env   # then edit .env with your credentials

# 3. Run migrations and start
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 core.asgi:application
```

---

## Run tests

```bash
pytest
```

Run a specific app's tests:

```bash
pytest apps/kitchen/tests/ -v
```

---

## Docker Compose

```bash
docker compose up --build
```

Starts PostgreSQL 15, Redis 7, and the Django app (Daphne ASGI) on port 8000. Migrations run automatically on startup.

---

## API Documentation

| URL | Description |
|-----|-------------|
| `/api/v1/docs/` | Swagger UI |
| `/api/v1/redoc/` | ReDoc |
| `/api/v1/schema/` | Raw OpenAPI YAML |
| `/api/v1/health/` | Health check (DB + Redis) |

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Django secret key |
| `JWT_SIGNING_KEY` | Yes | — | JWT HMAC signing key |
| `DATABASE_URL` | Yes | `postgres://postgres:postgres@127.0.0.1:5432/feast_db` | PostgreSQL connection URL |
| `REDIS_URL` | Yes | `redis://127.0.0.1:6379/0` | Redis connection URL |
| `ALLOWED_HOSTS` | Yes | `localhost,127.0.0.1` | Comma-separated allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | Yes | `http://localhost:5173` | Comma-separated allowed CORS origins |
| `MIDTRANS_SERVER_KEY` | Yes (payments) | — | Midtrans server key |
| `MIDTRANS_CLIENT_KEY` | Yes (payments) | — | Midtrans client key |
| `MIDTRANS_IS_PRODUCTION` | No | `False` | Set to `True` for live Midtrans environment |
| `CONN_MAX_AGE` | No | `60` | DB connection max age in seconds |
| `API_BASE_URL` | No | `https://api.feast.id` | Base URL shown in OpenAPI schema (prod only) |
| `DJANGO_SETTINGS_MODULE` | No | `core.settings.dev` | Settings module (`core.settings.prod` in Docker) |

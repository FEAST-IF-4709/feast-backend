# Stage 1 — build dependencies
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 — runtime
FROM python:3.12-slim
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /install /usr/local
COPY --chown=app:app . .

USER app
EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=core.settings.prod
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]

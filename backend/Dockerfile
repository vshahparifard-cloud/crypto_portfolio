FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# Dependencies are installed against a stub package so this layer only rebuilds
# when pyproject.toml changes; the real sources are copied over it below and the
# editable install already points at /app.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
 && pip install --upgrade pip && pip install -e ".[dev]"

COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

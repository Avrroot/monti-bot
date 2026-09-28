FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2 libxslt1.1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir .

FROM base AS bot
CMD ["python", "-m", "app.bot.main"]

FROM base AS worker
CMD ["arq", "app.workers.worker.WorkerSettings"]

FROM base AS api
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

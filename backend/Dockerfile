# Stage 1: Builder
FROM public.ecr.aws/docker/library/python:3.10-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use the official PyPI mirror with aggressive retries
RUN pip wheel --index-url=https://pypi.org/simple \
    --default-timeout=2000 --retries=50 \
    --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime
FROM public.ecr.aws/docker/library/python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev postgresql-client && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/* && \
    rm -rf /wheels

# Initialize TextBlob corpora
RUN python -m textblob.download_corpora

# Copy required application files and make entrypoint executable
# We copy files in order of how frequently they change to maximize layer caching.
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x ./entrypoint.sh

COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
COPY app/ ./app/

# Security: Run as non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
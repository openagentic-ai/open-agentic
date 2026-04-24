FROM python:3.12-slim AS base

WORKDIR /app

# Copy and install Python dependencies only (no apt-get needed for pure Python deps)
COPY pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || \
    pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.34.0" \
    "sse-starlette>=2.0.0" \
    "sqlalchemy[asyncio]>=2.0.36" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "pgvector>=0.3.6" \
    "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" \
    "python-multipart>=0.0.18" \
    "litellm>=1.55.0" \
    "pydantic>=2.10.0" \
    "pydantic-settings>=2.7.0" \
    "structlog>=24.4.0" \
    "prometheus-fastapi-instrumentator>=7.0.0" \
    "httpx>=0.28.0" \
    "python-dotenv>=1.0.1"

# Copy application code
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

ENV PYTHONPATH=/app/src
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
EXPOSE 8000

CMD ["uvicorn", "openagentic.main:app", "--host", "0.0.0.0", "--port", "8000"]

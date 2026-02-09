FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies from pyproject.toml
# Create minimal package structure so hatchling can resolve metadata
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py README.md && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    rm -rf app/__init__.py README.md

# Copy application code
COPY . .

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

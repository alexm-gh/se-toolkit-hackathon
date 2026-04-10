FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY llm/ ./llm/
COPY frontend/ ./frontend/
COPY sql/ ./sql/

# Load .env at runtime, but set sensible defaults
ENV USE_LLM=false \
    LLM_BASE_URL=http://localhost:42005/v1 \
    LLM_MODEL=coder-model \
    LLM_API_KEY=not-needed \
    DATABASE_URL=postgresql+asyncpg://ttmm_user:ttmm_password@db:5432/ttmm_database

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

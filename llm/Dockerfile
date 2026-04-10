FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install shared dependencies (from app's requirements)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install LLM-specific dependencies
RUN pip install --no-cache-dir openai

# Copy application code (LLM agent needs app/ for database and crud imports)
COPY app/ ./app/
COPY llm/ ./llm/

EXPOSE 8001

CMD ["uvicorn", "llm.main:app", "--host", "0.0.0.0", "--port", "8001"]

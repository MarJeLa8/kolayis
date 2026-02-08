FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY kolayis/ ./kolayis/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8000

# Run migrations then start the server
CMD alembic upgrade head && uvicorn kolayis.main:app --host 0.0.0.0 --port 8000

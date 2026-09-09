FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data/models

EXPOSE 8000

# Shell form (not exec-form JSON array) so $PORT expands - local
# docker-compose doesn't set PORT and falls back to 8000; hosting platforms
# that assign a dynamic port (Render, Railway, etc.) inject PORT at runtime
# and the container must bind to exactly that port to be routable.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

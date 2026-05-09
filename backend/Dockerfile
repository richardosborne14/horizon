# ── Development / Production backend Dockerfile ────────────────────────────────
# Uses Python 3.12 slim for a lean image.
# In development: source is volume-mounted, uvicorn runs with --reload.
# In production: source is copied in and uvicorn runs without --reload.

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# System deps needed to compile some Python packages (psycopg, bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command (overridden by docker-compose for dev/prod)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

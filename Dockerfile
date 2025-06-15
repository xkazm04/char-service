FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Use Cloud Run's preferred port
ENV PORT=8080
EXPOSE 8080

# Health check on correct port
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Start with dynamic port
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
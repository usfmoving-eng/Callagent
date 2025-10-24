# Use Python 3.10 slim image for smaller size
FROM python:3.10.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (if needed for any Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy .env file if exists
COPY .env* ./

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (default 5000, can be overridden)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Run with gunicorn (production-ready) - Optimized for AWS EC2 t3.xlarge (4 vCPUs)
# Using preload to initialize app once and share across workers (prevents Google Sheets rate limit)
CMD ["gunicorn", "--workers=4", "--threads=4", "--timeout=120", "--preload", "--bind=0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-", "app:app"]

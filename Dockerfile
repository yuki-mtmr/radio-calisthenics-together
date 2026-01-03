# Use official Python lightweight image
FROM python:3.11-slim

WORKDIR /app

# Copy source code and scripts
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Install dependencies (and the package itself)
RUN pip install --no-cache-dir .

# Ensure logs directory exists
RUN mkdir -p logs

# Set path to include src
ENV PYTHONPATH="/app/src"

# Default command (overridden by docker-compose or launchd)
CMD ["python", "scripts/check_status.py"]

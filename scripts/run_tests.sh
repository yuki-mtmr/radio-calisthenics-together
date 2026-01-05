#!/bin/bash
# Script to run tests inside the Docker container

echo "Running tests in Docker container (rct)..."
docker compose run --rm rct python -m pytest tests/

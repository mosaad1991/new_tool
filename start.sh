#!/bin/bash
set -e

echo "Checking environment..."

# Check required environment variables
required_vars=(
    "PORT"
    "REDIS_MERNA_URL"
    "REDIS_AQRABENO_URL"
    "REDIS_SWALF_URL"
    "REDIS_MOSAAD_URL"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set"
        exit 1
    fi
done

# Create necessary directories
mkdir -p logs temp

# Set default values for optional variables
export WORKERS=${WORKERS:-4}
export TIMEOUT=${TIMEOUT:-600}
export LOG_LEVEL=${LOG_LEVEL:-info}

echo "Starting server on port $PORT"
exec gunicorn app:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout $TIMEOUT \
    --log-level $LOG_LEVEL \
    --config gunicorn.conf.py
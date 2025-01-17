#!/bin/bash
set -e

echo "Checking environment..."

# إنشاء مجلد Prometheus إذا لم يكن موجودًا
PROMETHEUS_DIR=${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}
mkdir -p "$PROMETHEUS_DIR"
chmod 777 "$PROMETHEUS_DIR"

# تنظيف ملفات Prometheus القديمة
rm -f "$PROMETHEUS_DIR"/*.db

# التحقق من المتغيرات البيئية المطلوبة
required_vars=(
    "PORT"
    "REDIS_MERNA_URL"
    "REDIS_AQRABENO_URL"
    "REDIS_SWALF_URL"
    "REDIS_MOSAAD_URL"
    "PROMETHEUS_MULTIPROC_DIR"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set"
        exit 1
    fi
done

# إنشاء المجلدات الضرورية
mkdir -p logs temp

echo "Starting server on port $PORT"
exec gunicorn app:app \
    --workers ${WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout ${TIMEOUT:-600} \
    --log-level ${LOG_LEVEL:-info} \
    --config gunicorn.conf.py
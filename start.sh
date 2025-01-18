#!/bin/bash
set -e

echo "Checking environment..."

# تعيين المنفذ الافتراضي إذا لم يكن محدداً
export PORT=${PORT:-10000}

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
chmod 777 temp

# تهيئة مجلد prometheus
PROMETHEUS_DIR=${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}
mkdir -p "$PROMETHEUS_DIR"
chmod 777 "$PROMETHEUS_DIR"

# تنظيف ملفات Prometheus القديمة
rm -f "$PROMETHEUS_DIR"/*.db

# تعيين عدد العمال الافتراضي
export WORKERS=${WORKERS:-4}
export TIMEOUT=${TIMEOUT:-600}
export LOG_LEVEL=${LOG_LEVEL:-info}

# طباعة معلومات التكوين
echo "Starting server with configuration:"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Timeout: $TIMEOUT"
echo "Log level: $LOG_LEVEL"
echo "Prometheus directory: $PROMETHEUS_DIR"

# تشغيل الخادم
exec gunicorn app:app \
    --bind "0.0.0.0:$PORT" \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout $TIMEOUT \
    --log-level $LOG_LEVEL \
    --config gunicorn.conf.py
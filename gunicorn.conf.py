import multiprocessing
import os
from prometheus_client import multiprocess
from pathlib import Path

# ---------- Core Configuration ----------
wsgi_app = "app:app"
port = int(os.getenv('PORT', 10000))
bind = f"0.0.0.0:{port}"
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"

# ---------- Worker Settings ----------
worker_connections = int(os.getenv('CONNECTION_POOL_SIZE', '2000'))
worker_tmp_dir = "/dev/shm"  # Use memory for temp files
threads = int(os.getenv('THREADS', '4'))

# ---------- Timeout Configuration ----------
timeout = int(os.getenv('WORKER_TIMEOUT', '120'))  # 2 minutes
graceful_timeout = int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
keepalive = int(os.getenv('KEEPALIVE_TIMEOUT', '65'))

# ---------- SSL Configuration ----------
keyfile = os.getenv('SSL_KEYFILE')
certfile = os.getenv('SSL_CERTFILE')

# ---------- Process Naming ----------
proc_name = "youtube-shorts-generator"

# ---------- Server Mechanics ----------
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# ---------- Logging Configuration ----------
accesslog = "-"
errorlog = "-"
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s ms'
logger_class = 'gunicorn.glogging.Logger'
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'access': {
            'format': '%(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'error_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stderr'
        },
        'access_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'access',
            'stream': 'ext://sys.stdout'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'gunicorn.error': {
            'handlers': ['error_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gunicorn.access': {
            'handlers': ['access_console'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

# ---------- Process Management ----------
preload_app = True
reload = os.getenv('APP_ENV') == 'development'
max_requests = int(os.getenv('MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.getenv('MAX_REQUESTS_JITTER', '50'))

# ---------- Server Hooks ----------
def when_ready(server):
    """يتم تشغيله عندما يكون الخادم جاهزاً"""
    server.log.info(f"Server is ready. Listening on port {port}")
    server.log.info("Monitoring enabled.")

def on_starting(server):
    """إجراءات بدء التشغيل"""
    server.log.info(f"Starting YouTube Shorts Generator Server on port {port}")
    
    # تهيئة مجلد Prometheus
    prometheus_dir = os.getenv('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus')
    Path(prometheus_dir).mkdir(parents=True, exist_ok=True)
    
    # تنظيف ملفات المقاييس القديمة
    for f in Path(prometheus_dir).glob('*.db'):
        try:
            f.unlink()
        except Exception as e:
            server.log.warning(f"Could not delete {f}: {e}")

def on_reload(server):
    """إجراءات إعادة التحميل"""
    server.log.info("Reloading server configuration")
    multiprocess.mark_process_dead(server.pid)

def worker_abort(worker):
    """إدارة إيقاف العامل"""
    worker.log.warning(f"Worker {worker.pid} aborted")
    multiprocess.mark_process_dead(worker.pid)

def worker_int(worker):
    """إدارة إيقاف العامل بإشارة INT"""
    worker.log.info(f"Worker {worker.pid} received INT or QUIT signal")
    worker.log.info("Closing prometheus metrics")
    multiprocess.mark_process_dead(worker.pid)
    
    # السماح بوقت للإيقاف الآمن
    import threading
    timer = threading.Timer(graceful_timeout, worker.exit_code)
    timer.start()

def child_exit(server, worker):
    """تنظيف موارد العامل بعد الخروج"""
    multiprocess.mark_process_dead(worker.pid)
    server.log.info(f"Worker {worker.pid} exited")

def post_fork(server, worker):
    """إجراءات ما بعد تفريع العامل"""
    server.log.info(f"Worker {worker.pid} spawned")
    multiprocess.mark_process_dead(worker.pid)

# ---------- Environment Variables ----------
raw_env = [
    f"APP_ENV={os.getenv('APP_ENV', 'production')}",
    f"PROMETHEUS_MULTIPROC_DIR={os.getenv('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus')}",
    f"TASK_TIMEOUT={os.getenv('TASK_TIMEOUT', '300')}",
    f"REDIS_STREAM_MAX_LEN={os.getenv('REDIS_STREAM_MAX_LEN', '1000')}"
]

# ---------- Security Settings ----------
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# ---------- Server Mechanics ----------
forwarded_allow_ips = "*"  # Trust X-Forwarded-* headers
proxy_protocol = False
proxy_allow_ips = "*"

# ---------- SSL Configuration ----------
ssl_version = int(os.getenv('SSL_VERSION', '2'))  # Use TLS
ciphers = 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'

# ---------- Debugging ----------
spew = False
check_config = True
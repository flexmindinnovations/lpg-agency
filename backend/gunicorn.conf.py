import multiprocessing
import os

# Gunicorn config for FastAPI Production
# Ref: https://fastapi.tiangolo.com/deployment/server-workers/

bind = os.getenv("BIND", "0.0.0.0:8000")

# For I/O bound workloads (like FastAPI with WebSockets), the worker class should be uvicorn.
worker_class = "uvicorn.workers.UvicornWorker"

# Calculate workers based on CPU cores. We use 2 * cores + 1 as a rule of thumb.
# For high WebSocket concurrency, we want enough workers to handle parallel routing.
cores = multiprocessing.cpu_count()
workers_per_core = float(os.getenv("WORKERS_PER_CORE", "2"))
default_web_concurrency = workers_per_core * cores + 1
web_concurrency = int(os.getenv("WEB_CONCURRENCY", str(default_web_concurrency)))
workers = max(int(web_concurrency), 2)

# Connection Limits (Important for 100,000 Concurrent users)
# We need to ensure we can accept many connections per worker.
worker_connections = int(os.getenv("WORKER_CONNECTIONS", "50000"))

# Keepalive for proxies/LBs
keepalive = int(os.getenv("KEEPALIVE", "120"))

# Timeout
timeout = int(os.getenv("TIMEOUT", "120"))

# Logging
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"  # stdout
errorlog = "-"   # stderr

print(f"Starting Gunicorn with {workers} workers.")
print(f"Worker connections: {worker_connections}")

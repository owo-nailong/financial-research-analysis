#!/bin/sh
set -e

echo "[backend] waiting for database..."
python - <<'PY'
import os, time, sys
host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
use_sqlite = os.getenv("USE_SQLITE", "false").lower() in ("1", "true", "yes")
if use_sqlite:
    print("[backend] USE_SQLITE=true, skip MySQL wait")
    sys.exit(0)
import socket
for i in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[backend] MySQL {host}:{port} is up")
            sys.exit(0)
    except OSError:
        time.sleep(2)
print(f"[backend] MySQL {host}:{port} not ready, starting anyway")
PY

echo "[backend] starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port "${SERVER_PORT:-8000}" --workers 1

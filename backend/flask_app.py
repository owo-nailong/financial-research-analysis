"""
Secondary Flask service surface (health/status for ops), required by stack checklist.
Primary API remains FastAPI on port 8000.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend package path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify

from config import SERVER_CONFIG, LLM_CONFIG, OLLAMA_BASE_URL, MYSQL_CONFIG, USE_SQLITE
from database import check_db_health
from ollama_client import ollama_reachable
from rag_store import vector_store, rag_params

app = Flask(__name__)


@app.get("/health")
def health():
    db = check_db_health()
    ollama = ollama_reachable()
    return jsonify({
        "status": "ok" if db.get("ok") else "degraded",
        "service": "flask-secondary",
        "database": db,
        "ollama": ollama,
        "llm_model": LLM_CONFIG.get("model_name"),
        "ollama_base": OLLAMA_BASE_URL,
        "rag_chunks": vector_store.chunk_count,
        "rag_enabled": rag_params.get().get("enabled"),
        "use_sqlite": USE_SQLITE,
        "mysql_host": MYSQL_CONFIG.get("host"),
    })


@app.get("/")
def index():
    return jsonify({
        "service": "Financial Research Flask Surface",
        "endpoints": ["/health"],
        "note": "Primary API is FastAPI on port 8000",
    })


def run():
    port = int(os.getenv("FLASK_PORT", SERVER_CONFIG.get("flask_port", 5001)))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run()

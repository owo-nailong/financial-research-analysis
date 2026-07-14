"""
Financial Research Analysis System - Configuration
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root if present
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        with open(_env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value

# ============================================================
# Database - MySQL primary
# ============================================================
USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() in ("true", "1", "yes")

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "root"),
    "database": os.getenv("MYSQL_DATABASE", "financial_research"),
    "charset": "utf8mb4",
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 3600,
}

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DIR = DATA_DIR / "vector_store"
VECTOR_DIR.mkdir(parents=True, exist_ok=True)

if USE_SQLITE:
    SQLITE_PATH = DATA_DIR / "financial_research.db"
    DATABASE_URL = f"sqlite:///{SQLITE_PATH}"
else:
    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}"
        f"@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
        f"?charset={MYSQL_CONFIG['charset']}"
    )

MYSQL_URL = DATABASE_URL

# ============================================================
# Redis
# ============================================================
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "password": os.getenv("REDIS_PASSWORD", ""),
    "db": int(os.getenv("REDIS_DB", 0)),
    "decode_responses": True,
}

# ============================================================
# LLM / Ollama
# ============================================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
LLM_CONFIG = {
    "provider": LLM_PROVIDER,
    "model_name": os.getenv("LLM_MODEL", "qwen2.5:latest"),
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "base_url": os.getenv("LLM_BASE_URL", "") or OLLAMA_BASE_URL,
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
    "ollama_base_url": OLLAMA_BASE_URL,
}

EMBEDDING_CONFIG = {
    "model_name": os.getenv("EMBEDDING_MODEL", "embeddinggemma:latest"),
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "ollama_base_url": OLLAMA_BASE_URL,
}

# ============================================================
# RAG
# ============================================================
VECTOR_STORE_CONFIG = {
    "persist_directory": os.getenv("VECTOR_STORE_PATH", str(VECTOR_DIR)),
    "collection_name": "financial_docs",
    "chunk_size": int(os.getenv("RAG_CHUNK_SIZE", 800)),
    "chunk_overlap": int(os.getenv("RAG_CHUNK_OVERLAP", 120)),
    "top_k": int(os.getenv("RAG_TOP_K", 5)),
    "score_threshold": float(os.getenv("RAG_SCORE_THRESHOLD", 0.15)),
    "enabled": os.getenv("RAG_ENABLED", "true").lower() in ("true", "1", "yes"),
}

# ============================================================
# Auth
# ============================================================
AUTH_CONFIG = {
    "jwt_secret": os.getenv("JWT_SECRET", "financial-research-secret-change-in-prod"),
    "jwt_algorithm": "HS256",
    "token_expire_hours": int(os.getenv("TOKEN_EXPIRE_HOURS", 72)),
    "admin_username": os.getenv("ADMIN_USERNAME", "admin"),
    "admin_password": os.getenv("ADMIN_PASSWORD", "admin123"),
    "user_username": os.getenv("USER_USERNAME", "user"),
    "user_password": os.getenv("USER_PASSWORD", "user123"),
}

# ============================================================
# Data sources
# ============================================================
DATA_SOURCE_CONFIG = {
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    "news_api_key": os.getenv("NEWS_API_KEY", ""),
    "social_crawl_enabled": os.getenv("SOCIAL_CRAWL_ENABLED", "false").lower() == "true",
    "request_timeout": 30,
    "max_retries": 3,
    "retry_backoff": 2,
}

# ============================================================
# Server
# ============================================================
SERVER_CONFIG = {
    "host": os.getenv("SERVER_HOST", "0.0.0.0"),
    "port": int(os.getenv("SERVER_PORT", 8000)),
    "debug": os.getenv("DEBUG", "true").lower() == "true",
    "workers": int(os.getenv("WORKERS", 1)),
    "flask_port": int(os.getenv("FLASK_PORT", 5001)),
}

CACHE_CONFIG = {
    "default_ttl": int(os.getenv("CACHE_TTL", 3600)),
    "news_ttl": int(os.getenv("NEWS_CACHE_TTL", 1800)),
    "report_ttl": int(os.getenv("REPORT_CACHE_TTL", 86400)),
    "stock_ttl": int(os.getenv("STOCK_CACHE_TTL", 300)),
}

# Proxy hint for downloads
PROXY_URL = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or "http://127.0.0.1:7897"

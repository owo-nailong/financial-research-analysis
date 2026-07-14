"""
Financial Research Analysis System - launcher

Usage:
  python main.py                 # start FastAPI backend
  python main.py --flask         # start Flask secondary surface
  python main.py --seed          # seed multi-source + RAG index
  python main.py --check         # dependency check
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def load_dotenv():
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value
        print(f"[OK] loaded env: {env_file}")
    else:
        print("[INFO] no .env found, using defaults / environment")


def check_dependencies():
    missing = []
    for module in ["fastapi", "uvicorn", "sqlalchemy", "pymysql", "redis", "flask", "jwt", "numpy"]:
        try:
            __import__(module if module != "jwt" else "jwt")
        except ImportError:
            missing.append(module)
    if missing:
        print(f"[WARN] missing: {', '.join(missing)}")
        print(f"       pip install -r {BACKEND_DIR / 'requirements.txt'}")
        print("       if slow: set HTTP_PROXY=http://127.0.0.1:7897")
        return False
    print("[OK] core dependencies present")
    return True


def start_backend():
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    print(f"""
============================================================
 Financial Research Analysis System
 FastAPI : http://{host}:{port}
 Docs    : http://{host}:{port}/docs
 Flask   : python main.py --flask  (port {os.getenv('FLASK_PORT', '5001')})
 Frontend: cd frontend && npm run dev  -> http://localhost:5173
============================================================
""")
    import uvicorn
    uvicorn.run("main:app", host=host, port=port, reload=os.getenv("DEBUG", "true").lower() in ("1", "true", "yes"))


def start_flask():
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))
    from flask_app import run
    run()


def run_seed(force: bool = False):
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))
    from seed_data import seed_all
    print(seed_all(force=force, index_rag=True))


def main():
    parser = argparse.ArgumentParser(description="Financial Research Analysis System")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--force-seed", action="store_true")
    parser.add_argument("--flask", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    if args.port:
        os.environ["SERVER_PORT"] = str(args.port)

    if args.check:
        check_dependencies()
        return
    if args.seed or args.force_seed:
        run_seed(force=args.force_seed or args.seed)
        return
    if args.flask:
        start_flask()
        return

    if not check_dependencies():
        sys.exit(1)
    start_backend()


if __name__ == "__main__":
    main()

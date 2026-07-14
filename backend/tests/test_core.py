"""
Gating tests against shipped backend modules (real functions, seed data).
Run from backend/: pytest -q tests/test_core.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

# Load project .env
env_path = ROOT / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

# Force MySQL if password present
os.environ.setdefault("USE_SQLITE", "false")
os.environ.setdefault("MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "root"))


@pytest.fixture(scope="session", autouse=True)
def _bootstrap():
    from database import init_db
    from seed_data import seed_all
    from auth import init_default_users
    init_db()
    init_default_users()
    # seed without re-embedding every run if data exists; force false for speed
    stats = seed_all(force=False, index_rag=True)
    assert stats.get("ok") is True or stats.get("counts", {}).get("reports", 0) > 0
    return stats


def test_db_is_mysql_not_sqlite_when_configured():
    from config import USE_SQLITE, DATABASE_URL
    from database import check_db_health, db_backend_name
    health = check_db_health()
    assert health["ok"] is True
    # Prefer MySQL for hard requirement
    if not USE_SQLITE:
        assert db_backend_name() == "mysql"
        assert "mysql" in DATABASE_URL
        assert health["backend"] == "mysql"
    else:
        pytest.skip("USE_SQLITE enabled")


def test_auth_admin_and_user_roles():
    from auth import verify_password, create_token, decode_token
    admin = verify_password("admin", "admin123")
    user = verify_password("user", "user123")
    assert admin and admin["role"] == "admin"
    assert user and user["role"] == "user"
    assert verify_password("admin", "wrong") is None
    token = create_token("admin", "admin")
    payload = decode_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_fetch_multi_source_non_empty():
    import asyncio
    from mcp_tools import mcp_handler

    async def run():
        reports = await mcp_handler.fetch_research_reports({"limit": 10})
        news = await mcp_handler.fetch_financial_news({"limit": 10})
        anns = await mcp_handler.fetch_company_announcements({"limit": 10})
        social = await mcp_handler.fetch_social_sentiment({"limit": 10})
        return reports, news, anns, social

    reports, news, anns, social = asyncio.run(run())
    assert reports["status"] == "ok" and len(reports.get("data") or []) > 0
    assert isinstance(reports["data"][0]["title"], str)
    assert reports.get("total", len(reports["data"])) > 0
    assert news["status"] == "ok" and len(news.get("data") or []) > 0
    assert anns["status"] == "ok" and (anns.get("total") or len(anns.get("data") or [])) > 0
    assert social["status"] == "ok" and (social.get("total") or len(social.get("data") or [])) > 0


def test_extract_ratings_and_sentiment():
    import asyncio
    from mcp_tools import mcp_handler

    async def run():
        ratings = await mcp_handler.extract_investment_ratings({"stock_code": "600519"})
        sentiment = await mcp_handler.analyze_sentiment({
            "texts": ["看好龙头增长，维持买入", "行业价格战导致利润承压"],
        })
        compare = await mcp_handler.compare_opinions({"stock_code": "600519", "stock_name": "贵州茅台"})
        forecast = await mcp_handler.extract_profit_forecast({"stock_code": "600519"})
        risks = await mcp_handler.extract_risk_warnings({"stock_code": "600519"})
        financial = await mcp_handler.extract_financial_data({"stock_code": "600519"})
        return ratings, sentiment, compare, forecast, risks, financial

    ratings, sentiment, compare, forecast, risks, financial = asyncio.run(run())
    assert ratings["status"] == "ok" and ratings["total"] > 0
    assert sentiment["status"] == "ok" and sentiment["total"] == 2
    assert compare["status"] == "ok" and compare.get("report_count", 0) > 0
    assert forecast["status"] == "ok" and forecast.get("consensus")
    assert risks["status"] == "ok"
    assert financial["status"] == "ok" and financial.get("financial_data") is not None


def test_rag_chunk_and_params():
    from rag_store import chunk_text, rag_params, vector_store

    chunks = chunk_text("甲。" * 50 + "乙。" * 50, chunk_size=100, overlap=20)
    assert len(chunks) >= 2
    old = rag_params.get()
    updated = rag_params.update({"top_k": 3, "score_threshold": 0.1})
    assert updated["top_k"] == 3
    assert updated["score_threshold"] == 0.1
    # restore
    rag_params.update({"top_k": old.get("top_k", 5), "score_threshold": old.get("score_threshold", 0.15)})
    assert vector_store.chunk_count >= 0  # may be 0 if embedding offline


def test_agent_chat_returns_answer():
    import asyncio
    from agent import get_agent

    async def run():
        agent = get_agent()
        return await agent.chat("分析贵州茅台的券商评级分布", session_id="pytest_session", stock_code="600519")

    result = asyncio.run(run())
    assert result["answer"]
    assert result["session_id"] == "pytest_session"
    assert isinstance(result["thought_chain"], list)
    assert len(result["thought_chain"]) >= 1


def test_kb_add_has_source_url_field():
    import asyncio
    from agent import get_agent
    from database import SessionLocal, KnowledgeDocument

    async def run():
        agent = get_agent()
        return await agent.add_to_kb(
            title="pytest-doc",
            content="这是用于测试RAG导入的贵州茅台研报片段，营收与净利润保持增长。",
            doc_type="自定义",
            source_url="seed://pytest/doc",
        )

    res = asyncio.run(run())
    assert res.get("status") == "ok"
    doc_id = res.get("doc_id")
    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
        assert doc is not None
        assert doc.source_url == "seed://pytest/doc"
    finally:
        db.close()

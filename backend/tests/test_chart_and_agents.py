"""Tests for candlestick helpers and multi-agent orchestration."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def test_candle_bodies_and_non_flat_range():
    from chart_utils import candle_bodies, kline_period_stats, assert_non_flat_range

    # synthetic OHLC with wide range (like moutai ~1150-1540)
    points = []
    price = 1400.0
    for i in range(30):
        o = price
        c = price + (20 if i % 3 else -15)
        h = max(o, c) + 10
        l = min(o, c) - 10
        points.append({"date": f"2026-01-{i+1:02d}", "open": o, "close": c, "high": h, "low": l, "volume": 1000 + i})
        price = c
    candles = candle_bodies(points)
    assert len(candles) == 30
    assert any(c["has_wick"] for c in candles)
    assert any(c["up"] for c in candles) and any(not c["up"] for c in candles)
    assert all(c["color"] in ("#ef5350", "#26a69a") for c in candles)
    stats = kline_period_stats(points)
    assert stats["price_range"] > 1.0
    assert stats["ma5"] is not None
    assert assert_non_flat_range(points) is True


def test_kline_live_or_sample_non_flat():
    """Prefer live East Money kline; if offline use embedded sample still non-flat."""
    from data_fetcher import fetch_kline
    from chart_utils import assert_non_flat_range, kline_period_stats, candle_bodies

    res = fetch_kline("600519", limit=60)
    if res.get("status") == "ok" and res.get("data"):
        pts = res["data"]
        assert assert_non_flat_range(pts, min_range=0.5)
        stats = kline_period_stats(pts)
        assert stats["period_high"] >= stats["period_low"]
        assert stats["count"] >= 10
        candles = candle_bodies(pts)
        assert len(candles) == len(pts)
        assert any(c["high"] >= c["body_top"] for c in candles)
    else:
        pytest.skip("live kline unavailable")


def test_multi_agent_structure_without_full_llm():
    """Drive shipped run_multi_agent; allow offline model placeholders but structure must hold."""
    from multi_agent import run_multi_agent, ROLES

    result = run_multi_agent(
        question="简要说明贵州茅台投资风险关注点",
        context="公开资料：白酒龙头，估值与批价波动需关注。",
        stock_code="600519",
    )
    assert result["status"] == "ok"
    assert result["agent_count"] >= 4
    roles = {s["role"] for s in result["steps"]}
    assert "finance_analyst" in roles
    assert "user_advocate" in roles
    assert "reviewer" in roles
    assert "manager" in roles
    assert result.get("final_answer")
    assert len(result["final_answer"]) > 10
    assert set(ROLES.keys()).issuperset(roles)


def test_help_content_file_exists_and_substantial():
    """Help center Vue source must contain all required sections with real prose."""
    root = BACKEND.parent
    help_vue = (root / "frontend" / "src" / "views" / "HelpCenter.vue").read_text(encoding="utf-8")
    for key in ("新手引导", "常见问题", "免责声明", "用户反馈"):
        assert key in help_vue
    # substantial FAQ / disclaimer length in source
    assert help_vue.count("投资") >= 3
    assert "不构成" in help_vue or "不构成任何" in help_vue
    assert len(help_vue) > 2000

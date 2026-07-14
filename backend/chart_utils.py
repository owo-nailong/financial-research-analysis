"""
OHLC candlestick geometry helpers (A-share color convention: red up, green down).
Used by dashboard rendering logic tests and optional server-side precompute.
"""
from __future__ import annotations

from typing import Any


def compute_ma(closes: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < window:
            out.append(None)
        else:
            seg = closes[i + 1 - window : i + 1]
            out.append(round(sum(seg) / window, 4))
    return out


def kline_period_stats(points: list[dict]) -> dict[str, Any]:
    """Compute period high/low, latest, change%, MA5/MA20 from OHLC points."""
    if not points:
        return {
            "count": 0,
            "latest_close": None,
            "change_pct": None,
            "period_high": None,
            "period_low": None,
            "ma5": None,
            "ma20": None,
            "price_range": 0.0,
        }
    closes = [float(p["close"]) for p in points]
    highs = [float(p.get("high", p["close"])) for p in points]
    lows = [float(p.get("low", p["close"])) for p in points]
    ma5 = compute_ma(closes, 5)
    ma20 = compute_ma(closes, 20)
    first, last = closes[0], closes[-1]
    change_pct = ((last - first) / first * 100.0) if first else None
    ph, pl = max(highs), min(lows)
    return {
        "count": len(points),
        "latest_close": last,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "period_high": ph,
        "period_low": pl,
        "ma5": ma5[-1],
        "ma20": ma20[-1],
        "price_range": round(ph - pl, 4),
        "ma5_series": ma5,
        "ma20_series": ma20,
    }


def candle_bodies(points: list[dict]) -> list[dict]:
    """
    Build candle descriptors for rendering.
    Each item: open, close, high, low, up (bool), body_top, body_bottom, wick_high, wick_low
    """
    out = []
    for p in points:
        o = float(p["open"])
        c = float(p["close"])
        h = float(p.get("high", max(o, c)))
        l = float(p.get("low", min(o, c)))
        up = c >= o
        out.append({
            "date": p.get("date"),
            "open": o,
            "close": c,
            "high": h,
            "low": l,
            "up": up,
            "color": "#ef5350" if up else "#26a69a",
            "body_top": max(o, c),
            "body_bottom": min(o, c),
            "has_wick": h > max(o, c) or l < min(o, c),
            "has_body": abs(c - o) > 1e-9 or True,
        })
    return out


def assert_non_flat_range(points: list[dict], min_range: float = 1.0) -> bool:
    """True if price high-low span is non-degenerate (not flat)."""
    if len(points) < 2:
        return False
    stats = kline_period_stats(points)
    return (stats.get("price_range") or 0) > min_range

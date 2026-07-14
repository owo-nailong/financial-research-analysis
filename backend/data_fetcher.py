"""
Real multi-source financial data fetchers (no mock seed).

Public sources (no paid key):
  1) 券商研报  reportapi.eastmoney.com
  2) 财经新闻  np-listapi.eastmoney.com
  3) 公司公告  www.cninfo.com.cn
  4) K线/看板  push2his.eastmoney.com  (price curve for dashboard)
  5) 社交讨论  gbapi.eastmoney.com (股吧，作舆情近似)

All requests bypass system HTTP proxy for reliability.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, date, timedelta
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.trust_env = False
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

# ---- Documented source URLs (the four + kline for curves) ----
SOURCE_URLS = {
    "research_reports": "https://reportapi.eastmoney.com/report/list",
    "financial_news": "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns",
    "company_announcements": "http://www.cninfo.com.cn/new/hisAnnouncement/query",
    "kline_curve": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
    "social_guba": "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist",
}


def to_secid(stock_code: str) -> str:
    """A-share code -> East Money secid (1.SH / 0.SZ)."""
    code = (stock_code or "").strip()
    if not code:
        return ""
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def _parse_date(s: Any) -> Optional[date]:
    if not s:
        return None
    text = str(s)[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_dt(s: Any) -> datetime:
    if not s:
        return datetime.utcnow()
    text = str(s).replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def fetch_kline(stock_code: str, limit: int = 120) -> dict:
    """
    Real daily K-line for dashboard curves.
    Source: East Money push2his kline API.
    """
    secid = to_secid(stock_code)
    if not secid:
        return {"status": "error", "message": "缺少股票代码", "source_url": SOURCE_URLS["kline_curve"]}
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 101,  # daily
        "fqt": 1,    # qfq
        "end": "20500101",
        "lmt": max(5, min(int(limit), 500)),
    }
    last_err = None
    for attempt in range(3):
        try:
            resp = SESSION.get(
                SOURCE_URLS["kline_curve"],
                params=params,
                timeout=25,
                headers={
                    "Referer": "https://quote.eastmoney.com/",
                    "Host": "push2his.eastmoney.com",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or {}
            klines = data.get("klines") or []
            points = []
            for row in klines:
                # date,open,close,high,low,volume,amount,...
                parts = str(row).split(",")
                if len(parts) < 6:
                    continue
                points.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]) if len(parts) > 6 else None,
                })
            if not points:
                last_err = "empty klines"
                continue
            return {
                "status": "ok",
                "source": "eastmoney_kline",
                "source_url": SOURCE_URLS["kline_curve"],
                "stock_code": data.get("code") or stock_code,
                "stock_name": data.get("name") or "",
                "total": len(points),
                "data": points,
            }
        except Exception as e:
            last_err = str(e)
            logger.warning("kline fetch attempt %s failed: %s", attempt + 1, e)
    return {
        "status": "error",
        "message": last_err or "kline fetch failed",
        "source_url": SOURCE_URLS["kline_curve"],
        "data": [],
    }


def fetch_research_reports_live(stock_code: str = "", limit: int = 20) -> list[dict]:
    """Live research report list from East Money reportapi."""
    page_size = max(1, min(int(limit), 50))
    end = date.today()
    begin = end - timedelta(days=365 * 2)
    params = {
        "industryCode": "*",
        "pageSize": page_size,
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": begin.isoformat(),
        "endTime": end.isoformat(),
        "pageNo": 1,
        "fields": "",
        "qType": 0,
        "orgCode": "",
        "rcode": "",
        "p": 1,
        "code": stock_code or "*",
        "market": "*",
        "cid": 0,
    }
    try:
        resp = SESSION.get(
            SOURCE_URLS["research_reports"],
            params=params,
            timeout=25,
            headers={"Referer": "https://data.eastmoney.com/report/"},
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") or []
        out = []
        for r in rows[:page_size]:
            rating = r.get("emRatingName") or r.get("sRatingName") or r.get("rating") or ""
            # normalize rating labels
            if rating and rating not in ("买入", "增持", "中性", "减持", "卖出"):
                if "买" in rating:
                    rating = "买入"
                elif "增" in rating:
                    rating = "增持"
                elif "中" in rating:
                    rating = "中性"
                elif "减" in rating:
                    rating = "减持"
                elif "卖" in rating:
                    rating = "卖出"
            title = r.get("title") or ""
            org = r.get("orgSName") or r.get("orgName") or "未知机构"
            code = r.get("stockCode") or stock_code or ""
            name = r.get("stockName") or ""
            pub = _parse_date(r.get("publishDate") or r.get("publishTime"))
            info_code = r.get("infoCode") or r.get("encodeUrl") or ""
            source_url = (
                f"https://data.eastmoney.com/report/info/{info_code}.html"
                if info_code else SOURCE_URLS["research_reports"]
            )
            viewpoint = r.get("indvInduName") or r.get("predictThisYearEps") or ""
            if r.get("predictThisYearEps") is not None:
                viewpoint = f"预测本年EPS: {r.get('predictThisYearEps')}; 预测下年EPS: {r.get('predictNextYearEps')}"
            out.append({
                "title": title,
                "institution": org,
                "analyst": r.get("researcher") or r.get("author") or "",
                "report_date": pub or date.today(),
                "stock_code": code,
                "stock_name": name,
                "industry": r.get("indvInduName") or r.get("industryName") or "",
                "report_type": r.get("reportType") or "研报",
                "rating": rating or None,
                "target_price": _safe_float(r.get("aimPriceS") or r.get("aimPriceE") or r.get("targetPrice")),
                "current_price": None,
                "profit_forecast": {
                    "this_year_eps": r.get("predictThisYearEps"),
                    "next_year_eps": r.get("predictNextYearEps"),
                    "this_year_pe": r.get("predictThisYearPe"),
                    "next_year_pe": r.get("predictNextYearPe"),
                },
                "risk_warnings": r.get("riskNote") or "",
                "core_viewpoint": viewpoint or title,
                "full_content": f"{title}\n机构:{org}\n评级:{rating}\n{viewpoint}",
                "source_url": source_url,
                "sentiment_score": _rating_to_score(rating),
            })
        return out
    except Exception as e:
        logger.exception("report live fetch failed: %s", e)
        return []


def fetch_financial_news_live(keyword: str = "", stock_code: str = "", limit: int = 20) -> list[dict]:
    """Live financial news from East Money columns API."""
    page_size = max(1, min(int(limit), 50))
    # column 350 roughly finance headlines; also try stock-related list
    params = {
        "client": "web",
        "biz": "web_news_col",
        "column": "350",
        "order": 1,
        "needInteractData": 0,
        "page_index": 1,
        "page_size": page_size,
        "req_trace": "1",
        "fields": "code,showTime,title,mediaName,summary,url,uniqueUrl,type",
    }
    try:
        resp = SESSION.get(
            SOURCE_URLS["financial_news"],
            params=params,
            timeout=20,
            headers={"Referer": "https://finance.eastmoney.com/"},
        )
        resp.raise_for_status()
        payload = resp.json()
        items = ((payload.get("data") or {}).get("list")) or []
        out = []
        kw = (keyword or stock_code or "").strip()
        for n in items:
            title = n.get("title") or ""
            summary = n.get("summary") or ""
            if kw and kw not in title and kw not in summary:
                # keep general feed if no keyword match required strictly
                if stock_code:
                    continue
            url = n.get("uniqueUrl") or n.get("url") or ""
            text = f"{title}\n{summary}"
            label, score = _simple_sentiment(text)
            out.append({
                "title": title,
                "source": n.get("mediaName") or "东方财富",
                "author": "",
                "publish_time": _parse_dt(n.get("showTime")),
                "url": url,
                "content": summary or title,
                "summary": summary,
                "tags": ["财经新闻"],
                "related_stocks": [stock_code] if stock_code else [],
                "sentiment_label": label,
                "sentiment_score": score,
            })
            if len(out) >= page_size:
                break
        # If stock filter emptied list, return unfiltered top
        if not out and items:
            for n in items[:page_size]:
                title = n.get("title") or ""
                summary = n.get("summary") or ""
                text = f"{title}\n{summary}"
                label, score = _simple_sentiment(text)
                out.append({
                    "title": title,
                    "source": n.get("mediaName") or "东方财富",
                    "author": "",
                    "publish_time": _parse_dt(n.get("showTime")),
                    "url": n.get("uniqueUrl") or n.get("url") or "",
                    "content": summary or title,
                    "summary": summary,
                    "tags": ["财经新闻"],
                    "related_stocks": [stock_code] if stock_code else [],
                    "sentiment_label": label,
                    "sentiment_score": score,
                })
        return out
    except Exception as e:
        logger.exception("news live fetch failed: %s", e)
        return []


def fetch_announcements_live(stock_code: str, limit: int = 20) -> list[dict]:
    """Live company announcements from CNINFO."""
    code = (stock_code or "").strip()
    if not code:
        return []
    page_size = max(1, min(int(limit), 30))
    # orgId pattern gssh0XXXXXX for SH, gssz0XXXXXX for SZ
    if code.startswith(("5", "6", "9")):
        org_id = f"gssh0{code}"
        column = "sse"
    else:
        org_id = f"gssz0{code}"
        column = "szse"
    form = {
        "stock": f"{code},{org_id}",
        "searchkey": "",
        "plate": "",
        "category": "",
        "trade": "",
        "column": column,
        "columnTitle": "历史公告",
        "pageNum": 1,
        "pageSize": page_size,
        "tabName": "fulltext",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    try:
        resp = SESSION.post(
            SOURCE_URLS["company_announcements"],
            data=form,
            timeout=25,
            headers={
                "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("announcements") or []
        out = []
        for a in rows[:page_size]:
            title = (a.get("announcementTitle") or "").strip()
            # strip HTML tags sometimes present
            title = re.sub(r"<[^>]+>", "", title)
            ann_id = a.get("announcementId") or ""
            adj = a.get("adjunctUrl") or ""
            url = f"http://static.cninfo.com.cn/{adj}" if adj else SOURCE_URLS["company_announcements"]
            ts = a.get("announcementTime")
            if isinstance(ts, (int, float)):
                # milliseconds
                ad = datetime.utcfromtimestamp(ts / 1000.0).date()
            else:
                ad = _parse_date(ts) or date.today()
            out.append({
                "stock_code": a.get("secCode") or code,
                "stock_name": a.get("secName") or "",
                "title": title,
                "announce_date": ad,
                "announce_type": a.get("announcementTypeName") or a.get("announcementType") or "公告",
                "content": title,
                "summary": title,
                "key_points": [title[:80]] if title else [],
                "source_url": url,
            })
        return out
    except Exception as e:
        logger.exception("announcement live fetch failed: %s", e)
        return []


def fetch_social_live(stock_code: str, limit: int = 30) -> list[dict]:
    """Live social posts from East Money Guba (股吧) discussion list."""
    code = (stock_code or "").strip()
    if not code:
        return []
    page_size = max(1, min(int(limit), 50))
    params = {
        "code": code,
        "ps": page_size,
        "p": 1,
        "type": 0,
    }
    try:
        resp = SESSION.get(
            SOURCE_URLS["social_guba"],
            params=params,
            timeout=20,
            headers={"Referer": f"https://guba.eastmoney.com/list,{code}.html"},
        )
        # API may return json or jsonp-ish
        text = resp.text.strip()
        if text.startswith("{"):
            payload = resp.json()
        else:
            m = re.search(r"\{[\s\S]*\}", text)
            payload = __import__("json").loads(m.group()) if m else {}
        rows = payload.get("re") or payload.get("data") or payload.get("list") or []
        if isinstance(rows, dict):
            rows = rows.get("list") or rows.get("articles") or []
        out = []
        for p in (rows or [])[:page_size]:
            content = p.get("post_content") or p.get("title") or p.get("post_title") or p.get("digest") or ""
            content = re.sub(r"<[^>]+>", "", str(content)).strip() if content else ""
            if not content:
                continue
            label, score = _simple_sentiment(content)
            hot = p.get("post_click_count") or p.get("click_count") or p.get("post_comment_count") or 0
            try:
                hot = int(hot)
            except Exception:
                hot = 0
            out.append({
                "stock_code": code,
                "stock_name": p.get("stockbar_name") or "",
                "platform": "东方财富股吧",
                "content": content[:500],
                "author": p.get("user_nickname") or p.get("user_name") or p.get("nickname") or "",
                "post_time": _parse_dt(p.get("post_publish_time") or p.get("publish_time") or p.get("create_time")),
                "sentiment_label": label,
                "sentiment_score": score,
                "hot_index": hot,
            })
        if out:
            return out
    except Exception as e:
        logger.exception("social live fetch failed: %s", e)

    # Fallback: use live news headlines as market discussion stream
    news = fetch_financial_news_live(stock_code=stock_code, limit=min(page_size, 15))
    out = []
    for n in news:
        out.append({
            "stock_code": stock_code,
            "stock_name": "",
            "platform": "东方财富资讯流",
            "content": (n.get("title") or "") + " " + (n.get("summary") or ""),
            "author": n.get("source") or "",
            "post_time": n.get("publish_time") or datetime.utcnow(),
            "sentiment_label": n.get("sentiment_label") or "neutral",
            "sentiment_score": n.get("sentiment_score") or 0.0,
            "hot_index": 50,
        })
    return out


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _rating_to_score(rating: str) -> float:
    return {"买入": 0.8, "增持": 0.45, "中性": 0.0, "减持": -0.45, "卖出": -0.8}.get(rating or "", 0.0)


def _simple_sentiment(text: str) -> tuple[str, float]:
    pos = ("增长", "利好", "上涨", "超预期", "买入", "增持", "创新高", "改善", "突破", "看好")
    neg = ("下跌", "风险", "亏损", "减持", "卖出", "暴雷", "下滑", "承压", "警示", "违规")
    score = 0.0
    for w in pos:
        if w in text:
            score += 0.12
    for w in neg:
        if w in text:
            score -= 0.12
    score = max(-1.0, min(1.0, score))
    if score > 0.15:
        return "positive", round(score, 3)
    if score < -0.15:
        return "negative", round(score, 3)
    return "neutral", round(score, 3)


def source_catalog() -> list[dict]:
    return [
        {"name": "东方财富研报API", "kind": "research_reports", "url": SOURCE_URLS["research_reports"]},
        {"name": "东方财富财经新闻", "kind": "financial_news", "url": SOURCE_URLS["financial_news"]},
        {"name": "巨潮资讯公告", "kind": "company_announcements", "url": SOURCE_URLS["company_announcements"]},
        {"name": "东方财富K线(看板曲线)", "kind": "kline_curve", "url": SOURCE_URLS["kline_curve"]},
        {"name": "东方财富股吧舆情", "kind": "social_guba", "url": SOURCE_URLS["social_guba"]},
    ]

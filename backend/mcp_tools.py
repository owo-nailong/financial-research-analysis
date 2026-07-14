"""
MCP tool handlers: multi-source aggregation, extraction, sentiment, summary, RAG QA.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from config import CACHE_CONFIG, LLM_CONFIG
from database import (
    ResearchReport, FinancialNews, CompanyAnnouncement, SocialSentiment,
    KnowledgeDocument, InvestmentQA, ContentTemplate,
    RedisCache, SessionLocal,
)
from ollama_client import chat as ollama_chat
from rag_store import vector_store, rag_params, kb_status
from data_fetcher import (
    fetch_research_reports_live, fetch_financial_news_live,
    fetch_announcements_live, fetch_social_live, fetch_kline, source_catalog,
)

logger = logging.getLogger(__name__)

MCP_TOOL_DEFINITIONS = [
    {"name": "fetch_research_reports", "description": "抓取并解析券商研报", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "stock_name": {"type": "string"}, "industry": {"type": "string"},
        "start_date": {"type": "string"}, "end_date": {"type": "string"}, "limit": {"type": "integer", "default": 20},
    }}},
    {"name": "fetch_financial_news", "description": "抓取财经新闻", "inputSchema": {"type": "object", "properties": {
        "keyword": {"type": "string"}, "stock_code": {"type": "string"}, "start_date": {"type": "string"},
        "end_date": {"type": "string"}, "sentiment": {"type": "string"}, "limit": {"type": "integer", "default": 20},
    }}},
    {"name": "fetch_company_announcements", "description": "抓取公司公告", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "stock_name": {"type": "string"}, "announce_type": {"type": "string"},
        "start_date": {"type": "string"}, "end_date": {"type": "string"}, "limit": {"type": "integer", "default": 20},
    }}},
    {"name": "fetch_social_sentiment", "description": "抓取社交舆情", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "stock_name": {"type": "string"}, "platform": {"type": "string"},
        "start_date": {"type": "string"}, "end_date": {"type": "string"}, "limit": {"type": "integer", "default": 50},
    }}},
    {"name": "extract_financial_data", "description": "提取结构化财务数据", "inputSchema": {"type": "object", "properties": {
        "text": {"type": "string"}, "stock_code": {"type": "string"}, "report_id": {"type": "integer"},
    }}},
    {"name": "extract_profit_forecast", "description": "提取盈利预测", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "report_ids": {"type": "array", "items": {"type": "integer"}},
    }}},
    {"name": "extract_investment_ratings", "description": "提取投资评级统计", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"},
    }}},
    {"name": "extract_risk_warnings", "description": "提取风险提示", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "report_ids": {"type": "array", "items": {"type": "integer"}},
    }}},
    {"name": "compare_opinions", "description": "多研报观点对比", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "stock_name": {"type": "string"}, "start_date": {"type": "string"},
        "end_date": {"type": "string"}, "limit": {"type": "integer", "default": 10},
    }}},
    {"name": "analyze_sentiment", "description": "文本情感分析", "inputSchema": {"type": "object", "properties": {
        "texts": {"type": "array", "items": {"type": "string"}}, "context": {"type": "string"},
    }}},
    {"name": "aggregate_market_sentiment", "description": "综合市场情绪", "inputSchema": {"type": "object", "properties": {
        "stock_code": {"type": "string"}, "stock_name": {"type": "string"}, "days": {"type": "integer", "default": 30},
    }}},
    {"name": "generate_summary", "description": "生成摘要", "inputSchema": {"type": "object", "properties": {
        "text": {"type": "string"}, "doc_type": {"type": "string"}, "style": {"type": "string"}, "max_length": {"type": "integer"},
    }}},
    {"name": "investment_qa", "description": "投资问答", "inputSchema": {"type": "object", "properties": {
        "question": {"type": "string"}, "stock_code": {"type": "string"}, "session_id": {"type": "string"}, "use_rag": {"type": "boolean"},
    }}},
    {"name": "search_knowledge_base", "description": "知识库检索", "inputSchema": {"type": "object", "properties": {
        "query": {"type": "string"}, "top_k": {"type": "integer"}, "doc_type": {"type": "string"}, "stock_code": {"type": "string"},
    }}},
    {"name": "generate_content", "description": "内容生成", "inputSchema": {"type": "object", "properties": {
        "content_type": {"type": "string"}, "stock_code": {"type": "string"}, "stock_name": {"type": "string"},
        "template_id": {"type": "integer"}, "extra_params": {"type": "object"},
    }}},
    {"name": "batch_analyze_portfolio", "description": "组合批量分析", "inputSchema": {"type": "object", "properties": {
        "stocks": {"type": "array"}, "days": {"type": "integer"},
    }}},
]


class MCPToolHandler:
    @staticmethod
    def _cache_key(tool_name: str, params: dict) -> str:
        raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return f"mcp:{tool_name}:{hashlib.md5(raw.encode()).hexdigest()[:16]}"

    @staticmethod
    def _call_llm(prompt: str, system_prompt: str = "你是专业的金融分析师。请用中文回答。") -> str:
        """Prefer local Ollama; fallback to cloud keys if configured."""
        try:
            return ollama_chat(prompt, system_prompt=system_prompt)
        except Exception as e:
            logger.warning("[LLM] Ollama failed: %s", e)

        api_key = LLM_CONFIG.get("api_key", "")
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                resp = client.messages.create(
                    model=LLM_CONFIG.get("model_name", "claude-3-5-sonnet-latest"),
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=LLM_CONFIG.get("temperature", 0.2),
                    max_tokens=LLM_CONFIG.get("max_tokens", 4096),
                )
                return resp.content[0].text.strip()
            except Exception as e:
                logger.warning("[LLM] Anthropic failed: %s", e)

        # Deterministic offline fallback for demos without LLM
        return (
            "[离线摘要] 基于本地知识库与结构化数据的分析要点：\n"
            f"问题/文本片段：{prompt[:400]}\n"
            "请确保 Ollama 已启动并加载 qwen2.5 模型以获得完整智能回答。\n"
            "投资有风险，以上内容不构成投资建议。"
        )

    def _seed_reports_if_external_empty(self, params: dict) -> list[dict]:
        """Return structured sample from DB (seed-backed aggregation)."""
        return []  # DB path already primary

    async def fetch_research_reports(self, params: dict) -> dict:
        cache = await RedisCache.get_instance()
        key = self._cache_key("fetch_research_reports", params)
        cached = await cache.get(key)
        if cached:
            data = json.loads(cached)
            return {"status": "ok", "source": "cache", "total": len(data), "data": data}

        # 1) live crawl (东方财富研报)
        live_rows = fetch_research_reports_live(
            stock_code=params.get("stock_code") or "",
            limit=params.get("limit", 20),
        )
        db = SessionLocal()
        try:
            if live_rows:
                for item in live_rows:
                    exists = db.query(ResearchReport).filter(
                        ResearchReport.title == item["title"],
                        ResearchReport.institution == item["institution"],
                        ResearchReport.report_date == item["report_date"],
                    ).first()
                    if exists:
                        continue
                    db.add(ResearchReport(**item))
                db.commit()

            query = db.query(ResearchReport)
            if params.get("stock_code"):
                query = query.filter(ResearchReport.stock_code == params["stock_code"])
            if params.get("stock_name"):
                query = query.filter(ResearchReport.stock_name.like(f"%{params['stock_name']}%"))
            if params.get("industry"):
                query = query.filter(ResearchReport.industry == params["industry"])
            if params.get("start_date"):
                query = query.filter(ResearchReport.report_date >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(ResearchReport.report_date <= params["end_date"])
            reports = query.order_by(ResearchReport.report_date.desc()).limit(params.get("limit", 20)).all()
            data = [{
                "id": r.id, "title": r.title, "institution": r.institution, "analyst": r.analyst,
                "report_date": str(r.report_date), "stock_code": r.stock_code, "stock_name": r.stock_name,
                "industry": r.industry, "report_type": r.report_type, "rating": r.rating,
                "target_price": r.target_price, "current_price": r.current_price,
                "profit_forecast": r.profit_forecast, "risk_warnings": r.risk_warnings,
                "core_viewpoint": r.core_viewpoint, "sentiment_score": r.sentiment_score,
                "source_url": r.source_url, "full_content": (r.full_content or "")[:2000],
            } for r in reports]
            if data:
                await cache.set(key, data, CACHE_CONFIG["report_ttl"])
            return {
                "status": "ok",
                "source": "live+database" if live_rows else "database",
                "live_fetched": len(live_rows),
                "total": len(data),
                "data": data,
                "source_catalog": source_catalog(),
            }
        finally:
            db.close()

    async def fetch_financial_news(self, params: dict) -> dict:
        cache = await RedisCache.get_instance()
        key = self._cache_key("fetch_financial_news", params)
        cached = await cache.get(key)
        if cached:
            data = json.loads(cached)
            return {"status": "ok", "source": "cache", "total": len(data), "data": data}

        live_rows = fetch_financial_news_live(
            keyword=params.get("keyword") or "",
            stock_code=params.get("stock_code") or "",
            limit=params.get("limit", 20),
        )
        db = SessionLocal()
        try:
            if live_rows:
                for item in live_rows:
                    exists = db.query(FinancialNews).filter(FinancialNews.title == item["title"]).first()
                    if exists:
                        continue
                    db.add(FinancialNews(**item))
                db.commit()

            query = db.query(FinancialNews)
            if params.get("keyword"):
                kw = f"%{params['keyword']}%"
                query = query.filter((FinancialNews.title.like(kw)) | (FinancialNews.content.like(kw)))
            if params.get("stock_code"):
                query = query.filter(FinancialNews.related_stocks.like(f"%{params['stock_code']}%"))
            if params.get("sentiment"):
                query = query.filter(FinancialNews.sentiment_label == params["sentiment"])
            if params.get("start_date"):
                query = query.filter(FinancialNews.publish_time >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(FinancialNews.publish_time <= params["end_date"])
            news_list = query.order_by(FinancialNews.publish_time.desc()).limit(params.get("limit", 20)).all()
            data = [{
                "id": n.id, "title": n.title, "source": n.source, "author": n.author,
                "publish_time": str(n.publish_time), "url": n.url, "summary": n.summary,
                "content": (n.content or "")[:1500], "tags": n.tags, "related_stocks": n.related_stocks,
                "sentiment_label": n.sentiment_label, "sentiment_score": n.sentiment_score,
            } for n in news_list]
            await cache.set(key, data, CACHE_CONFIG["news_ttl"])
            return {
                "status": "ok",
                "source": "live+database" if live_rows else "database",
                "live_fetched": len(live_rows),
                "total": len(data),
                "data": data,
            }
        finally:
            db.close()

    async def fetch_company_announcements(self, params: dict) -> dict:
        stock_code = params.get("stock_code") or ""
        live_rows = fetch_announcements_live(stock_code, limit=params.get("limit", 20)) if stock_code else []
        db = SessionLocal()
        try:
            if live_rows:
                for item in live_rows:
                    # strip non-model fields
                    row = {k: v for k, v in item.items() if k != "source_url"}
                    exists = db.query(CompanyAnnouncement).filter(
                        CompanyAnnouncement.stock_code == row["stock_code"],
                        CompanyAnnouncement.title == row["title"],
                        CompanyAnnouncement.announce_date == row["announce_date"],
                    ).first()
                    if exists:
                        continue
                    db.add(CompanyAnnouncement(**row))
                db.commit()

            query = db.query(CompanyAnnouncement)
            if params.get("stock_code"):
                query = query.filter(CompanyAnnouncement.stock_code == params["stock_code"])
            if params.get("stock_name"):
                query = query.filter(CompanyAnnouncement.stock_name.like(f"%{params['stock_name']}%"))
            if params.get("announce_type"):
                query = query.filter(CompanyAnnouncement.announce_type == params["announce_type"])
            if params.get("start_date"):
                query = query.filter(CompanyAnnouncement.announce_date >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(CompanyAnnouncement.announce_date <= params["end_date"])
            rows = query.order_by(CompanyAnnouncement.announce_date.desc()).limit(params.get("limit", 20)).all()
            data = [{
                "id": a.id, "stock_code": a.stock_code, "stock_name": a.stock_name, "title": a.title,
                "announce_date": str(a.announce_date), "announce_type": a.announce_type,
                "summary": a.summary, "key_points": a.key_points, "content": (a.content or "")[:2000],
            } for a in rows]
            return {
                "status": "ok",
                "source": "live+database" if live_rows else "database",
                "live_fetched": len(live_rows),
                "total": len(data),
                "data": data,
            }
        finally:
            db.close()

    async def fetch_social_sentiment(self, params: dict) -> dict:
        stock_code = params.get("stock_code") or ""
        live_rows = fetch_social_live(stock_code, limit=params.get("limit", 50)) if stock_code else []
        db = SessionLocal()
        try:
            if live_rows:
                for item in live_rows:
                    exists = db.query(SocialSentiment).filter(
                        SocialSentiment.stock_code == item.get("stock_code"),
                        SocialSentiment.content == item.get("content"),
                    ).first()
                    if exists:
                        continue
                    db.add(SocialSentiment(**item))
                db.commit()

            query = db.query(SocialSentiment)
            if params.get("stock_code"):
                query = query.filter(SocialSentiment.stock_code == params["stock_code"])
            if params.get("stock_name"):
                query = query.filter(SocialSentiment.stock_name.like(f"%{params['stock_name']}%"))
            if params.get("platform") and params["platform"] != "全部":
                query = query.filter(SocialSentiment.platform == params["platform"])
            if params.get("start_date"):
                query = query.filter(SocialSentiment.post_time >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(SocialSentiment.post_time <= params["end_date"])
            posts = query.order_by(SocialSentiment.hot_index.desc()).limit(params.get("limit", 50)).all()
            stats = {"positive": 0, "neutral": 0, "negative": 0}
            post_list = []
            for p in posts:
                label = p.sentiment_label or "neutral"
                stats[label] = stats.get(label, 0) + 1
                post_list.append({
                    "id": p.id, "platform": p.platform, "content": p.content, "author": p.author,
                    "post_time": str(p.post_time), "sentiment_label": p.sentiment_label,
                    "sentiment_score": p.sentiment_score, "hot_index": p.hot_index,
                    "stock_code": p.stock_code, "stock_name": p.stock_name,
                })
            return {
                "status": "ok",
                "source": "live+database" if live_rows else "database",
                "live_fetched": len(live_rows),
                "total": len(post_list),
                "sentiment_stats": stats,
                "data": post_list,
            }
        finally:
            db.close()

    async def extract_financial_data(self, params: dict) -> dict:
        text = params.get("text") or ""
        stock_code = params.get("stock_code", "")
        if not text and params.get("report_id"):
            db = SessionLocal()
            try:
                report = db.query(ResearchReport).filter(ResearchReport.id == params["report_id"]).first()
                if report:
                    text = report.full_content or report.core_viewpoint or ""
                    stock_code = stock_code or report.stock_code or ""
            finally:
                db.close()
        if not text and stock_code:
            db = SessionLocal()
            try:
                report = db.query(ResearchReport).filter(ResearchReport.stock_code == stock_code).order_by(
                    ResearchReport.report_date.desc()
                ).first()
                if report:
                    text = report.full_content or report.core_viewpoint or ""
            finally:
                db.close()
        if not text:
            return {"status": "error", "message": "未提供文本且未找到关联研报"}

        # Rule-based extraction first (works without LLM)
        financial_data = self._regex_financial(text)
        prompt = f"""从以下文本提取财务指标，返回纯JSON：
{text[:6000]}
字段：revenue, revenue_yoy, net_profit, net_profit_yoy, roe, gross_margin, debt_ratio, eps, pe_ratio, pb_ratio, operating_cash_flow
未提及填null。"""
        try:
            llm_output = self._call_llm(prompt)
            m = re.search(r"\{[\s\S]*\}", llm_output)
            if m:
                parsed = json.loads(m.group())
                financial_data.update({k: v for k, v in parsed.items() if v is not None})
        except Exception as e:
            logger.warning("extract financial llm: %s", e)
        return {"status": "ok", "stock_code": stock_code, "financial_data": financial_data}

    @staticmethod
    def _regex_financial(text: str) -> dict:
        out = {}
        patterns = {
            "revenue": r"营收[^\d]{0,8}(\d+(?:\.\d+)?)\s*亿",
            "net_profit": r"(?:净利|净利润)[^\d]{0,8}(\d+(?:\.\d+)?)\s*亿",
            "eps": r"EPS[^\d]{0,6}(\d+(?:\.\d+)?)",
            "roe": r"ROE[^\d]{0,6}(\d+(?:\.\d+)?)\s*%?",
        }
        for k, pat in patterns.items():
            m = re.search(pat, text, re.I)
            if m:
                out[k] = float(m.group(1))
        return out

    async def extract_profit_forecast(self, params: dict) -> dict:
        stock_code = params.get("stock_code", "")
        report_ids = params.get("report_ids") or []
        db = SessionLocal()
        try:
            query = db.query(ResearchReport)
            if stock_code:
                query = query.filter(ResearchReport.stock_code == stock_code)
            if report_ids:
                query = query.filter(ResearchReport.id.in_(report_ids))
            reports = query.order_by(ResearchReport.report_date.desc()).limit(10).all()
            forecasts = [{
                "institution": r.institution, "report_date": str(r.report_date),
                "rating": r.rating, "target_price": r.target_price, "profit_forecast": r.profit_forecast,
            } for r in reports]
            prices = [r.target_price for r in reports if r.target_price]
            consensus = {
                "avg_target_price": round(sum(prices) / len(prices), 2) if prices else None,
                "max_target_price": max(prices) if prices else None,
                "min_target_price": min(prices) if prices else None,
                "institution_count": len(reports),
            }
            return {"status": "ok", "stock_code": stock_code, "forecasts": forecasts, "consensus": consensus}
        finally:
            db.close()

    async def extract_investment_ratings(self, params: dict) -> dict:
        stock_code = params.get("stock_code", "")
        db = SessionLocal()
        try:
            query = db.query(ResearchReport)
            if stock_code:
                query = query.filter(ResearchReport.stock_code == stock_code)
            if params.get("start_date"):
                query = query.filter(ResearchReport.report_date >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(ResearchReport.report_date <= params["end_date"])
            reports = query.all()
            rating_count = {"买入": 0, "增持": 0, "中性": 0, "减持": 0, "卖出": 0}
            target_prices, details = [], []
            for r in reports:
                rating = r.rating or "未评级"
                rating_count[rating] = rating_count.get(rating, 0) + 1
                if r.target_price:
                    target_prices.append(r.target_price)
                details.append({
                    "institution": r.institution, "report_date": str(r.report_date),
                    "rating": rating, "target_price": r.target_price, "analyst": r.analyst,
                })
            return {
                "status": "ok", "stock_code": stock_code, "total": len(reports),
                "rating_distribution": rating_count,
                "target_price_range": {
                    "min": min(target_prices) if target_prices else None,
                    "max": max(target_prices) if target_prices else None,
                    "avg": round(sum(target_prices) / len(target_prices), 2) if target_prices else None,
                },
                "details": details,
            }
        finally:
            db.close()

    async def extract_risk_warnings(self, params: dict) -> dict:
        stock_code = params.get("stock_code", "")
        report_ids = params.get("report_ids") or []
        db = SessionLocal()
        try:
            query = db.query(ResearchReport)
            if stock_code:
                query = query.filter(ResearchReport.stock_code == stock_code)
            if report_ids:
                query = query.filter(ResearchReport.id.in_(report_ids))
            reports = query.limit(20).all()
            all_risks = [{
                "report_id": r.id, "institution": r.institution,
                "report_date": str(r.report_date), "risks": r.risk_warnings,
            } for r in reports if r.risk_warnings]

            if all_risks:
                combined = "\n---\n".join(f"[{r['institution']}] {r['risks']}" for r in all_risks)
                # heuristic categories + LLM refine
                categories = {"宏观风险": [], "行业风险": [], "公司经营风险": [], "估值风险": []}
                for r in all_risks:
                    text = r["risks"]
                    if any(k in text for k in ("宏观", "政策", "监管", "消费复苏")):
                        categories["宏观风险"].append(text)
                    if any(k in text for k in ("行业", "竞争", "价格战", "出清")):
                        categories["行业风险"].append(text)
                    if any(k in text for k in ("经营", "渠道", "库存", "供应链", "动销")):
                        categories["公司经营风险"].append(text)
                    if any(k in text for k in ("估值", "回调", "批价")):
                        categories["估值风险"].append(text)
                    if not any(categories[c] and categories[c][-1] == text for c in categories):
                        categories["公司经营风险"].append(text)
                try:
                    prompt = f"将风险分类为宏观/行业/公司经营/估值，返回JSON：\n{combined[:5000]}"
                    out = self._call_llm(prompt)
                    m = re.search(r"\{[\s\S]*\}", out)
                    if m:
                        categories = json.loads(m.group())
                except Exception:
                    pass
            else:
                categories = {"info": "未找到风险提示数据"}
            return {"status": "ok", "stock_code": stock_code, "raw_risks": all_risks, "categorized_risks": categories}
        finally:
            db.close()

    async def compare_opinions(self, params: dict) -> dict:
        stock_code = params.get("stock_code", "")
        stock_name = params.get("stock_name", "")
        db = SessionLocal()
        try:
            query = db.query(ResearchReport)
            if stock_code:
                query = query.filter(ResearchReport.stock_code == stock_code)
            if params.get("start_date"):
                query = query.filter(ResearchReport.report_date >= params["start_date"])
            if params.get("end_date"):
                query = query.filter(ResearchReport.report_date <= params["end_date"])
            reports = query.order_by(ResearchReport.report_date.desc()).limit(params.get("limit", 10)).all()
            if not reports:
                return {"status": "ok", "message": f"未找到 {stock_code} 的研报", "report_count": 0, "comparison": {}}

            institutions = [r.institution for r in reports]
            ratings = [r.rating for r in reports if r.rating]
            prices = [r.target_price for r in reports if r.target_price]
            opinions = "\n".join(
                f"【{r.institution}|{r.report_date}|{r.rating}】{r.core_viewpoint or ''}" for r in reports
            )
            comparison = {
                "consensus": "多数机构看好龙头基本面与份额优势。" if ratings.count("买入") + ratings.count("增持") >= len(ratings) / 2 else "机构观点分化。",
                "divergence": f"目标价区间 {min(prices) if prices else '-'} ~ {max(prices) if prices else '-'}",
                "rating_summary": {k: ratings.count(k) for k in set(ratings)},
                "key_debate": "增长持续性与估值合理性",
                "overall_sentiment": "偏多" if sum(1 for r in ratings if r in ("买入", "增持")) >= len(ratings) / 2 else "中性",
            }
            try:
                prompt = f"对比{stock_name}({stock_code})研报观点，JSON字段consensus,divergence,rating_summary,key_debate,overall_sentiment：\n{opinions[:7000]}"
                out = self._call_llm(prompt)
                m = re.search(r"\{[\s\S]*\}", out)
                if m:
                    comparison = json.loads(m.group())
            except Exception as e:
                logger.warning("compare llm: %s", e)
            return {
                "status": "ok", "stock_code": stock_code, "stock_name": stock_name,
                "report_count": len(reports), "institutions": institutions, "comparison": comparison,
            }
        finally:
            db.close()

    async def analyze_sentiment(self, params: dict) -> dict:
        texts = params.get("texts") or []
        if not texts:
            return {"status": "error", "message": "请提供待分析文本"}
        results = []
        dist = {"positive": 0, "neutral": 0, "negative": 0}
        pos_words = ("增长", "买入", "看好", "提升", "领先", "机会", "亮眼", "积极")
        neg_words = ("风险", "下降", "承压", "担忧", "减持", "卖出", "疲软", "价格战")
        for text in texts:
            score = 0.0
            for w in pos_words:
                if w in text:
                    score += 0.15
            for w in neg_words:
                if w in text:
                    score -= 0.15
            score = max(-1.0, min(1.0, score))
            label = "positive" if score > 0.15 else ("negative" if score < -0.15 else "neutral")
            try:
                out = self._call_llm(
                    f'分析情感，返回JSON {{"sentiment":"positive|neutral|negative","score":-1到1,"confidence":0到1,"keywords":[],"reason":""}}：\n{text[:2000]}'
                )
                m = re.search(r"\{[\s\S]*\}", out)
                if m:
                    parsed = json.loads(m.group())
                    label = parsed.get("sentiment", label)
                    score = float(parsed.get("score", score))
                    results.append({"text": text[:200], **parsed})
                    dist[label] = dist.get(label, 0) + 1
                    continue
            except Exception:
                pass
            results.append({
                "text": text[:200], "sentiment": label, "score": round(score, 3),
                "confidence": 0.55, "keywords": [], "reason": "规则评分",
            })
            dist[label] = dist.get(label, 0) + 1
        return {"status": "ok", "total": len(texts), "distribution": dist, "results": results}

    async def aggregate_market_sentiment(self, params: dict) -> dict:
        stock_code = params.get("stock_code", "")
        stock_name = params.get("stock_name", "")
        days = int(params.get("days", 30))
        cutoff = date.today() - timedelta(days=days)
        db = SessionLocal()
        try:
            reports = db.query(ResearchReport).filter(
                ResearchReport.stock_code == stock_code,
                ResearchReport.report_date >= cutoff,
            ).all() if stock_code else []
            news = db.query(FinancialNews).filter(FinancialNews.publish_time >= datetime.combine(cutoff, datetime.min.time())).all()
            if stock_code:
                news = [n for n in news if n.related_stocks and stock_code in (n.related_stocks or [])]
            social = db.query(SocialSentiment).filter(
                SocialSentiment.stock_code == stock_code,
                SocialSentiment.post_time >= datetime.combine(cutoff, datetime.min.time()),
            ).all() if stock_code else []

            rating_map = {"买入": 1.0, "增持": 0.5, "中性": 0.0, "减持": -0.5, "卖出": -1.0}
            rs = [rating_map.get(r.rating, 0) for r in reports]
            ns = [n.sentiment_score or 0 for n in news]
            ss = [s.sentiment_score or 0 for s in social]
            avg_r = round(sum(rs) / len(rs), 3) if rs else 0.0
            avg_n = round(sum(ns) / len(ns), 3) if ns else 0.0
            avg_s = round(sum(ss) / len(ss), 3) if ss else 0.0
            composite = round(avg_r * 0.4 + avg_n * 0.3 + avg_s * 0.3, 3)

            def interpret(score: float) -> str:
                if score > 0.3:
                    return "偏多"
                if score < -0.3:
                    return "偏空"
                return "中性"

            return {
                "status": "ok", "stock_code": stock_code, "stock_name": stock_name, "period_days": days,
                "sentiment_index": {
                    "composite": composite, "interpretation": interpret(composite),
                    "breakdown": {
                        "research_reports": {"count": len(reports), "score": avg_r},
                        "financial_news": {"count": len(news), "score": avg_n},
                        "social_sentiment": {"count": len(social), "score": avg_s},
                    },
                },
                "rating_distribution": {
                    k: sum(1 for r in reports if r.rating == k) for k in ("买入", "增持", "中性", "减持", "卖出")
                },
            }
        finally:
            db.close()

    async def generate_summary(self, params: dict) -> dict:
        text = params.get("text") or ""
        if not text:
            return {"status": "error", "message": "请提供待摘要文本"}
        style = params.get("style", "专业")
        max_length = int(params.get("max_length", 500))
        doc_type = params.get("doc_type", "自动")
        prompt = f"为以下{doc_type}生成{style}风格摘要，不超过{max_length}字：\n{text[:8000]}"
        summary = self._call_llm(prompt)
        return {
            "status": "ok", "doc_type": doc_type, "style": style,
            "summary": summary, "original_length": len(text), "summary_length": len(summary),
        }

    async def search_knowledge_base(self, params: dict) -> dict:
        query = params.get("query") or ""
        top_k = int(params.get("top_k") or rag_params.get().get("top_k", 5))
        doc_type = params.get("doc_type", "全部")
        if not query:
            return {"status": "error", "message": "请提供搜索查询"}

        results = []
        # Vector RAG first
        try:
            if rag_params.get().get("enabled", True):
                results = vector_store.search(query, top_k=top_k, doc_type=doc_type)
        except Exception as e:
            logger.warning("[RAG] vector search failed: %s", e)

        # Keyword fallback / supplement
        if len(results) < top_k:
            db = SessionLocal()
            try:
                keyword = f"%{query}%"
                q = db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "active")
                if doc_type != "全部":
                    q = q.filter(KnowledgeDocument.doc_type == doc_type)
                docs = q.filter(
                    (KnowledgeDocument.title.like(keyword)) | (KnowledgeDocument.content.like(keyword))
                ).limit(top_k).all()
                seen = {str(r.get("doc_id")) for r in results}
                for d in docs:
                    if str(d.id) in seen:
                        continue
                    results.append({
                        "id": d.id, "doc_id": str(d.id), "title": d.title, "doc_type": d.doc_type,
                        "content": (d.content or "")[:1500], "tags": d.tags,
                        "related_stocks": d.related_stocks, "source_url": d.source_url or "",
                        "file_path": d.file_path or "", "score": 0.5, "search_method": "keyword",
                    })
                    if len(results) >= top_k:
                        break
            finally:
                db.close()
        return {"status": "ok", "query": query, "total": len(results), "data": results}

    async def investment_qa(self, params: dict) -> dict:
        question = params.get("question") or ""
        session_id = params.get("session_id", "default")
        use_rag = params.get("use_rag", True)
        if not question:
            return {"status": "error", "message": "请提供问题"}

        sources = []
        rag_context = ""
        if use_rag:
            kb = await self.search_knowledge_base({"query": question, "top_k": rag_params.get().get("top_k", 5)})
            if kb.get("data"):
                rag_context = "\n\n---\n".join(
                    f"[来源:{d.get('doc_type')}|{d.get('title')}|url={d.get('source_url','')}]\n{d.get('content','')[:1000]}"
                    for d in kb["data"]
                )
                sources = [{
                    "title": d.get("title"), "doc_type": d.get("doc_type"),
                    "score": d.get("score"), "source_url": d.get("source_url"),
                    "search_method": d.get("search_method"),
                } for d in kb["data"]]

        system_prompt = (
            "你是金融投资分析助手。基于参考资料回答，给出数据与逻辑；"
            "资料不足时说明。末尾附免责声明：投资有风险，以上分析不构成投资建议。"
        )
        user_prompt = f"用户问题：{question}\n\n参考资料：\n{rag_context or '（未检索到资料）'}"
        answer = self._call_llm(user_prompt, system_prompt=system_prompt)

        db = SessionLocal()
        try:
            db.add(InvestmentQA(
                session_id=session_id, question=question, answer=answer,
                sources=sources, related_stocks=[params.get("stock_code")] if params.get("stock_code") else None,
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        return {
            "status": "ok", "session_id": session_id, "question": question,
            "answer": answer, "sources": sources, "rag_used": use_rag,
        }

    async def generate_content(self, params: dict) -> dict:
        content_type = params.get("content_type", "研报摘要")
        stock_code = params.get("stock_code", "")
        stock_name = params.get("stock_name", "")
        template_id = params.get("template_id")
        extra_params = params.get("extra_params") or {}
        db = SessionLocal()
        try:
            template_prompt = None
            if template_id:
                t = db.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()
                if t:
                    template_prompt = t.prompt_template
            report_data = []
            if stock_code:
                reports = db.query(ResearchReport).filter(ResearchReport.stock_code == stock_code).order_by(
                    ResearchReport.report_date.desc()
                ).limit(5).all()
                report_data = [{
                    "institution": r.institution, "rating": r.rating,
                    "target_price": r.target_price, "core_viewpoint": r.core_viewpoint,
                } for r in reports]
        finally:
            db.close()

        if not template_prompt:
            defaults = {
                "研报摘要": "请基于以下数据生成{stock_name}研报摘要：概况、业绩、评级、要点、风险。",
                "投资建议": "请生成{stock_name}投资建议：逻辑、估值、目标价、操作建议。",
                "行业分析": "请生成行业分析：现状、竞争、趋势、机会风险。",
                "市场简报": "请生成市场简报：大盘、热点、资金、公告。",
            }
            template_prompt = defaults.get(content_type, defaults["研报摘要"])
        prompt = template_prompt.format(stock_name=stock_name or "指定标的", stock_code=stock_code or "")
        if report_data:
            prompt += f"\n参考数据：{json.dumps(report_data, ensure_ascii=False)}"
        if extra_params:
            prompt += f"\n额外要求：{json.dumps(extra_params, ensure_ascii=False)}"
        generated = self._call_llm(prompt, system_prompt="你是专业金融内容撰写专家。")
        return {
            "status": "ok", "content_type": content_type, "stock_code": stock_code,
            "stock_name": stock_name, "generated_content": generated,
        }

    async def batch_analyze_portfolio(self, params: dict) -> dict:
        stocks = params.get("stocks") or []
        days = int(params.get("days", 30))
        results = []
        for stock in stocks:
            code = stock.get("code") or stock.get("stock_code") or ""
            name = stock.get("name") or stock.get("stock_name") or ""
            if not code:
                continue
            sentiment = await self.aggregate_market_sentiment({"stock_code": code, "stock_name": name, "days": days})
            ratings = await self.extract_investment_ratings({"stock_code": code})
            results.append({
                "stock_code": code, "stock_name": name,
                "sentiment_index": sentiment.get("sentiment_index", {}),
                "rating_distribution": ratings.get("rating_distribution", {}),
                "target_price_range": ratings.get("target_price_range", {}),
            })
        return {"status": "ok", "total_stocks": len(results), "results": results}

    async def dispatch(self, tool_name: str, params: dict) -> dict:
        method_map = {
            "fetch_research_reports": self.fetch_research_reports,
            "fetch_financial_news": self.fetch_financial_news,
            "fetch_company_announcements": self.fetch_company_announcements,
            "fetch_social_sentiment": self.fetch_social_sentiment,
            "extract_financial_data": self.extract_financial_data,
            "extract_profit_forecast": self.extract_profit_forecast,
            "extract_investment_ratings": self.extract_investment_ratings,
            "extract_risk_warnings": self.extract_risk_warnings,
            "compare_opinions": self.compare_opinions,
            "analyze_sentiment": self.analyze_sentiment,
            "aggregate_market_sentiment": self.aggregate_market_sentiment,
            "generate_summary": self.generate_summary,
            "investment_qa": self.investment_qa,
            "search_knowledge_base": self.search_knowledge_base,
            "generate_content": self.generate_content,
            "batch_analyze_portfolio": self.batch_analyze_portfolio,
        }
        handler = method_map.get(tool_name)
        if not handler:
            return {"status": "error", "message": f"未知工具: {tool_name}"}
        try:
            return await handler(params)
        except Exception as e:
            logger.exception("tool=%s", tool_name)
            return {"status": "error", "message": str(e)}


mcp_handler = MCPToolHandler()

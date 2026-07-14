"""
FastAPI application entry for Financial Research Analysis System.
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mcp_tools import mcp_handler, MCP_TOOL_DEFINITIONS
from agent import get_agent, FinancialAnalysisAgent
from database import (
    init_db, RedisCache, SessionLocal, check_db_health,
    KnowledgeDocument, ContentTemplate, InvestmentQA,
    ResearchReport, FinancialNews, CompanyAnnouncement, SocialSentiment,
)
from models import (
    LoginRequest, FetchReportsRequest, FetchNewsRequest, FetchAnnouncementsRequest,
    FetchSocialRequest, ExtractFinancialRequest, ExtractForecastRequest,
    ExtractRatingsRequest, ExtractRiskRequest, CompareOpinionsRequest,
    SentimentRequest, MarketSentimentRequest, SummaryRequest, InvestmentQARequest,
    KnowledgeSearchRequest, ContentGenerateRequest, PortfolioAnalysisRequest,
    AgentChatRequest, AgentChatResponse, KnowledgeAddRequest,
    TemplateCreateRequest, TemplateUpdateRequest, RagParamsUpdate, CreateUserRequest,
    ChangePasswordRequest, AdminSetPasswordRequest,
)
from config import (
    SERVER_CONFIG, UPLOAD_DIR, AUTH_CONFIG, LLM_CONFIG, OLLAMA_BASE_URL,
    REDIS_CONFIG, BASE_DIR,
)
from auth import (
    verify_password, create_token, require_user, require_admin,
    get_current_user, list_users_safe, create_user, init_default_users,
    change_own_password, admin_set_password,
)
from crypto_auth import get_public_key_pem, decrypt_password_b64
from rag_store import rag_params, vector_store, kb_status
from ollama_client import ollama_reachable
from seed_data import seed_all
from data_fetcher import fetch_kline, source_catalog, search_stocks, resolve_stock_query
from chart_utils import kline_period_stats
from multi_agent import run_multi_agent
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[App] init db...")
    init_db()
    init_default_users()
    try:
        # only seed content templates by default; no fake seed:// rows
        stats = seed_all(force=False, index_rag=False)
        logger.info("[App] seed: %s", stats)
    except Exception as e:
        logger.warning("[App] seed skipped: %s", e)
    try:
        await RedisCache.get_instance()
    except Exception as e:
        logger.warning("[App] redis: %s", e)
    yield
    logger.info("[App] shutdown")


app = FastAPI(
    title="金融研报智能分析与投资决策辅助系统",
    description="FastAPI + LangChain Agent + RAG + Ollama",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_financial_agent() -> FinancialAnalysisAgent:
    return get_agent()


# -------------------- Auth --------------------
def _require_encrypted_password(password: Optional[str], password_encrypted: Optional[str]) -> str:
    """Reject plaintext passwords; only accept RSA-OAEP ciphertext."""
    if password and str(password).strip():
        raise HTTPException(
            status_code=400,
            detail="禁止明文传输密码，请使用 RSA-OAEP 加密后的 password_encrypted 字段",
        )
    if not password_encrypted:
        raise HTTPException(status_code=400, detail="缺少 password_encrypted")
    try:
        return decrypt_password_b64(password_encrypted)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/auth/public-key", tags=["认证"])
async def auth_public_key():
    """RSA public key (PEM) for client-side password encryption (RSA-OAEP SHA-256)."""
    return {
        "status": "ok",
        "algorithm": "RSA-OAEP",
        "hash": "SHA-256",
        "public_key_pem": get_public_key_pem(),
    }


@app.post("/api/auth/login", tags=["认证"])
async def login(req: LoginRequest):
    plain = _require_encrypted_password(req.password, req.password_encrypted)
    user = verify_password(req.username, plain)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["username"], user["role"])
    return {
        "status": "ok",
        "token": token,
        "user": user,
    }


@app.get("/api/auth/me", tags=["认证"])
async def me(user: dict = Depends(require_user)):
    return {"status": "ok", "user": user}


@app.post("/api/auth/change-password", tags=["认证"])
async def change_password(req: ChangePasswordRequest, user: dict = Depends(require_user)):
    """Any logged-in user can change their own password (encrypted transport)."""
    try:
        old_pw = decrypt_password_b64(req.old_password_encrypted)
        new_pw = decrypt_password_b64(req.new_password_encrypted)
        change_own_password(user["username"], old_pw, new_pw)
        return {"status": "ok", "message": "密码已更新"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/auth/admin/set-password", tags=["认证"])
async def admin_reset_password(req: AdminSetPasswordRequest, user: dict = Depends(require_admin)):
    """Admin can set any user's password (encrypted transport)."""
    try:
        new_pw = decrypt_password_b64(req.new_password_encrypted)
        admin_set_password(req.username, new_pw)
        return {"status": "ok", "message": f"已重置用户 {req.username} 的密码"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/auth/users", tags=["认证"])
async def users_list(user: dict = Depends(require_admin)):
    return {"status": "ok", "data": list_users_safe()}


@app.post("/api/auth/users", tags=["认证"])
async def users_create(req: CreateUserRequest, user: dict = Depends(require_admin)):
    try:
        plain = _require_encrypted_password(req.password, req.password_encrypted)
        created = create_user(req.username, plain, req.role, req.display_name or "")
        return {"status": "ok", "user": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------- Health --------------------
@app.get("/api/health", tags=["系统"])
async def health_check():
    db_h = check_db_health()
    redis = await RedisCache.get_instance()
    ollama = ollama_reachable()
    return {
        "status": "ok" if db_h.get("ok") else "degraded",
        "service": "金融研报智能分析系统",
        "version": "2.0.0",
        "tools_count": len(MCP_TOOL_DEFINITIONS),
        "database": db_h,
        "redis": {
            "ok": redis.available,
            "host": REDIS_CONFIG.get("host", "localhost"),
            "port": REDIS_CONFIG.get("port", 6379),
        },
        "ollama": ollama,
        "llm": {
            "provider": LLM_CONFIG.get("provider"),
            "model": LLM_CONFIG.get("model_name"),
            "base_url": OLLAMA_BASE_URL,
        },
        "rag": {
            "enabled": rag_params.get().get("enabled"),
            "chunks": vector_store.chunk_count,
            "docs": vector_store.doc_count,
        },
    }


@app.get("/api/tools", tags=["系统"])
async def list_tools(user: dict = Depends(require_user)):
    return {"total": len(MCP_TOOL_DEFINITIONS), "tools": [
        {"name": t["name"], "description": t["description"]} for t in MCP_TOOL_DEFINITIONS
    ]}


@app.post("/api/admin/seed", tags=["系统"])
async def admin_seed(force: bool = False, user: dict = Depends(require_admin)):
    return seed_all(force=force, index_rag=True)


# -------------------- Fetch --------------------
@app.post("/api/fetch/reports", tags=["多源信息聚合"])
async def fetch_reports(req: FetchReportsRequest, user: dict = Depends(require_user)):
    return await mcp_handler.fetch_research_reports(req.model_dump(exclude_none=True))


@app.post("/api/fetch/news", tags=["多源信息聚合"])
async def fetch_news(req: FetchNewsRequest, user: dict = Depends(require_user)):
    return await mcp_handler.fetch_financial_news(req.model_dump(exclude_none=True))


@app.post("/api/fetch/announcements", tags=["多源信息聚合"])
async def fetch_announcements(req: FetchAnnouncementsRequest, user: dict = Depends(require_user)):
    return await mcp_handler.fetch_company_announcements(req.model_dump(exclude_none=True))


@app.post("/api/fetch/social", tags=["多源信息聚合"])
async def fetch_social(req: FetchSocialRequest, user: dict = Depends(require_user)):
    return await mcp_handler.fetch_social_sentiment(req.model_dump(exclude_none=True))


# -------------------- Extract / Analysis --------------------
@app.post("/api/extract/financial", tags=["关键信息提取"])
async def extract_financial(req: ExtractFinancialRequest, user: dict = Depends(require_user)):
    return await mcp_handler.extract_financial_data(req.model_dump(exclude_none=True))


@app.post("/api/extract/forecast", tags=["关键信息提取"])
async def extract_forecast(req: ExtractForecastRequest, user: dict = Depends(require_user)):
    return await mcp_handler.extract_profit_forecast(req.model_dump(exclude_none=True))


@app.post("/api/extract/ratings", tags=["关键信息提取"])
async def extract_ratings(req: ExtractRatingsRequest, user: dict = Depends(require_user)):
    return await mcp_handler.extract_investment_ratings(req.model_dump(exclude_none=True))


@app.post("/api/extract/risks", tags=["关键信息提取"])
async def extract_risks(req: ExtractRiskRequest, user: dict = Depends(require_user)):
    return await mcp_handler.extract_risk_warnings(req.model_dump(exclude_none=True))


@app.post("/api/analysis/compare", tags=["观点分析与情感"])
async def compare_opinions(req: CompareOpinionsRequest, user: dict = Depends(require_user)):
    return await mcp_handler.compare_opinions(req.model_dump(exclude_none=True))


@app.post("/api/analysis/sentiment", tags=["观点分析与情感"])
async def analyze_sentiment(req: SentimentRequest, user: dict = Depends(require_user)):
    return await mcp_handler.analyze_sentiment(req.model_dump(exclude_none=True))


@app.post("/api/analysis/market-sentiment", tags=["观点分析与情感"])
async def market_sentiment(req: MarketSentimentRequest, user: dict = Depends(require_user)):
    return await mcp_handler.aggregate_market_sentiment(req.model_dump(exclude_none=True))


# -------------------- Generate / QA --------------------
@app.post("/api/generate/summary", tags=["智能摘要与内容生成"])
async def generate_summary(req: SummaryRequest, user: dict = Depends(require_user)):
    return await mcp_handler.generate_summary(req.model_dump(exclude_none=True))


@app.post("/api/generate/content", tags=["智能摘要与内容生成"])
async def generate_content(req: ContentGenerateRequest, user: dict = Depends(require_user)):
    return await mcp_handler.generate_content(req.model_dump(exclude_none=True))


@app.post("/api/generate/portfolio", tags=["智能摘要与内容生成"])
async def batch_portfolio(req: PortfolioAnalysisRequest, user: dict = Depends(require_user)):
    return await mcp_handler.batch_analyze_portfolio(req.model_dump(exclude_none=True))


@app.post("/api/qa/investment", tags=["智能问答"])
async def investment_qa(req: InvestmentQARequest, user: dict = Depends(require_user)):
    return await mcp_handler.investment_qa(req.model_dump(exclude_none=True))


@app.post("/api/kb/search", tags=["知识库"])
async def search_knowledge_base(req: KnowledgeSearchRequest, user: dict = Depends(require_user)):
    return await mcp_handler.search_knowledge_base(req.model_dump(exclude_none=True))


# -------------------- Agent --------------------
@app.post("/api/agent/chat", response_model=AgentChatResponse, tags=["Agent"])
async def agent_chat(req: AgentChatRequest, user: dict = Depends(require_user),
                     agent: FinancialAnalysisAgent = Depends(get_financial_agent)):
    result = await agent.chat(
        question=req.question, session_id=req.session_id,
        stock_code=req.stock_code, use_rag=req.use_rag,
    )
    return AgentChatResponse(**result)


@app.post("/api/agent/quick-report", tags=["Agent"])
async def quick_report(
    stock_code: str = Query(...),
    stock_name: str = Query(""),
    user: dict = Depends(require_user),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    return await agent.quick_report(stock_code, stock_name)


@app.get("/api/agent/sessions/{session_id}", tags=["Agent"])
async def get_session_history(session_id: str, user: dict = Depends(require_user),
                              agent: FinancialAnalysisAgent = Depends(get_financial_agent)):
    session = agent.get_session(session_id)
    return {
        "session_id": session_id,
        "created_at": session.created_at.isoformat(),
        "message_count": len(session.history),
        "history": session.history[-20:],
        "context": session.context,
    }


@app.delete("/api/agent/sessions/{session_id}", tags=["Agent"])
async def clear_session(session_id: str, user: dict = Depends(require_user),
                        agent: FinancialAnalysisAgent = Depends(get_financial_agent)):
    agent.clear_session(session_id)
    return {"status": "ok", "message": f"会话 {session_id} 已清除"}


# -------------------- Knowledge Base --------------------
@app.post("/api/kb/add", tags=["知识库管理"])
async def kb_add(req: KnowledgeAddRequest, user: dict = Depends(require_admin),
                 agent: FinancialAnalysisAgent = Depends(get_financial_agent)):
    return await agent.add_to_kb(
        title=req.title, content=req.content, doc_type=req.doc_type,
        tags=req.tags, related_stocks=req.related_stocks,
        source_url=req.source_url or "",
    )


@app.get("/api/kb/list", tags=["知识库管理"])
async def kb_list(
    doc_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_disabled: bool = Query(False, description="管理员可查看已停用文档"),
    user: dict = Depends(require_user),
):
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument)
        # Never list permanently-removed legacy rows if any remain as archived
        query = query.filter(KnowledgeDocument.status != "archived")
        # 普通用户只看启用文档；管理员可查看停用（disabled）文档
        if user.get("role") != "admin" or not include_disabled:
            query = query.filter(KnowledgeDocument.status == "active")
        if doc_type:
            query = query.filter(KnowledgeDocument.doc_type == doc_type)
        total = query.count()
        docs = query.order_by(KnowledgeDocument.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {
            "total": total, "page": page, "page_size": page_size,
            "data": [{
                "id": d.id, "title": d.title, "doc_type": d.doc_type,
                "content_preview": (d.content or "")[:300],
                "tags": d.tags, "related_stocks": d.related_stocks,
                "source_url": d.source_url or "",
                "file_path": d.file_path or "",
                "vector_id": d.vector_id or "",
                "status": d.status or "active",
                "enabled": (d.status or "active") == "active",
                "created_at": str(d.created_at),
            } for d in docs],
        }
    finally:
        db.close()


@app.get("/api/kb/status", tags=["知识库管理"])
async def knowledge_status(
    probe_remote: bool = Query(
        False,
        description="是否探测远程 URL 可达性（默认关闭，避免阻塞整个 API）",
    ),
    user: dict = Depends(require_user),
):
    # Run in thread so any residual blocking I/O cannot freeze the event loop
    import asyncio
    return await asyncio.to_thread(kb_status, probe_remote)


@app.get("/api/kb/{doc_id}", tags=["知识库管理"])
async def kb_get(doc_id: int, user: dict = Depends(require_user)):
    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == doc_id, KnowledgeDocument.status == "active",
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {
            "id": doc.id, "title": doc.title, "doc_type": doc.doc_type,
            "content": doc.content, "tags": doc.tags, "related_stocks": doc.related_stocks,
            "source_url": doc.source_url, "file_path": doc.file_path,
            "created_at": str(doc.created_at), "updated_at": str(doc.updated_at),
        }
    finally:
        db.close()


@app.patch("/api/kb/{doc_id}/toggle", tags=["知识库管理"])
async def kb_toggle(
    doc_id: int,
    enabled: bool = Query(..., description="true=启用并参与RAG，false=停用并从索引移除"),
    user: dict = Depends(require_admin),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    """启用/停用知识库文档（开关）。停用后不参与检索，可再次启用。"""
    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        if enabled:
            doc.status = "active"
            db.commit()
            # 重新写入向量索引
            if doc.content:
                try:
                    from rag_store import vector_store
                    vector_store.add_document(
                        doc_id=str(doc.id),
                        title=doc.title or "",
                        content=doc.content or "",
                        source_url=doc.source_url or "",
                        file_path=doc.file_path or "",
                        doc_type=doc.doc_type or "自定义",
                        tags=doc.tags or [],
                        related_stocks=doc.related_stocks or [],
                    )
                    doc.vector_id = str(doc.id)
                    db.commit()
                except Exception as e:
                    logger.warning("reindex on enable failed: %s", e)
            return {"status": "ok", "doc_id": doc_id, "enabled": True, "message": "已启用"}
        else:
            doc.status = "disabled"
            db.commit()
            try:
                from rag_store import vector_store
                vector_store.delete_document(str(doc_id))
            except Exception as e:
                logger.warning("vector remove on disable: %s", e)
            return {"status": "ok", "doc_id": doc_id, "enabled": False, "message": "已停用"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.delete("/api/kb/{doc_id}", tags=["知识库管理"])
async def kb_delete(doc_id: int, user: dict = Depends(require_admin),
                    agent: FinancialAnalysisAgent = Depends(get_financial_agent)):
    return await agent.remove_from_kb(doc_id)


@app.post("/api/kb/import", tags=["知识库管理"])
async def kb_batch_import(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("自定义"),
    source_url: str = Form(""),
    user: dict = Depends(require_admin),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    """Batch import text/markdown/pdf-ish files into KB + vector index (admin only)."""
    results = []
    for f in files:
        try:
            raw = await f.read()
            # decode text
            content = None
            for enc in ("utf-8", "gbk", "latin-1"):
                try:
                    content = raw.decode(enc)
                    break
                except Exception:
                    continue
            if content is None:
                results.append({"filename": f.filename, "status": "error", "message": "无法解码文件"})
                continue
            safe_name = f"{uuid.uuid4().hex}_{Path(f.filename or 'upload.txt').name}"
            dest = UPLOAD_DIR / safe_name
            dest.write_bytes(raw)
            title = Path(f.filename or "imported").stem
            res = await agent.add_to_kb(
                title=title,
                content=content,
                doc_type=doc_type or "自定义",
                source_url=source_url or f"import://{f.filename}",
                file_path=str(dest),
            )
            results.append({"filename": f.filename, **res})
        except Exception as e:
            results.append({"filename": f.filename, "status": "error", "message": str(e)})
    ok = sum(1 for r in results if r.get("status") == "ok")
    return {"status": "ok", "imported": ok, "total": len(results), "results": results}


# -------------------- RAG params --------------------
@app.get("/api/rag/params", tags=["RAG"])
async def get_rag_params(user: dict = Depends(require_user)):
    from rag_store import _display_path
    return {"status": "ok", "params": rag_params.get(), "store": {
        "document_count": vector_store.doc_count,
        "chunk_count": vector_store.chunk_count,
        "path": _display_path(vector_store.directory),
    }}


@app.put("/api/rag/params", tags=["RAG"])
async def update_rag_params(req: RagParamsUpdate, user: dict = Depends(require_admin)):
    try:
        updated = rag_params.update(req.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "params": updated}


# -------------------- Templates --------------------
@app.post("/api/templates/create", tags=["模板管理"])
async def template_create(req: TemplateCreateRequest, user: dict = Depends(require_admin)):
    db = SessionLocal()
    try:
        template = ContentTemplate(
            name=req.name, category=req.category,
            prompt_template=req.prompt_template, output_format=req.output_format,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return {"status": "ok", "template_id": template.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/templates/list", tags=["模板管理"])
async def template_list(category: str = Query(None), user: dict = Depends(require_user)):
    db = SessionLocal()
    try:
        query = db.query(ContentTemplate)
        if category:
            query = query.filter(ContentTemplate.category == category)
        templates = query.all()
        return {"total": len(templates), "data": [{
            "id": t.id, "name": t.name, "category": t.category,
            "prompt_template": t.prompt_template, "output_format": t.output_format,
        } for t in templates]}
    finally:
        db.close()


@app.put("/api/templates/{template_id}", tags=["模板管理"])
async def template_update(template_id: int, req: TemplateUpdateRequest, user: dict = Depends(require_admin)):
    db = SessionLocal()
    try:
        template = db.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        for key, value in req.model_dump(exclude_none=True).items():
            setattr(template, key, value)
        db.commit()
        return {"status": "ok", "message": "模板已更新"}
    finally:
        db.close()


@app.get("/api/dashboard/summary", tags=["仪表盘"])
async def dashboard_summary(user: dict = Depends(require_user)):
    db = SessionLocal()
    try:
        return {
            "total_reports": db.query(ResearchReport).count(),
            "total_news": db.query(FinancialNews).count(),
            "total_announcements": db.query(CompanyAnnouncement).count(),
            "total_social_posts": db.query(SocialSentiment).count(),
            "total_kb_docs": db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "active").count(),
            "total_qa": db.query(InvestmentQA).count(),
            "vector_chunks": vector_store.chunk_count,
            "data_sources": source_catalog(),
        }
    finally:
        db.close()


@app.get("/api/dashboard/stock-search", tags=["仪表盘"])
async def dashboard_stock_search(
    q: str = Query(..., min_length=1, description="股票代码或名称关键词"),
    limit: int = Query(10, ge=1, le=30),
    user: dict = Depends(require_user),
):
    """按代码/名称搜索 A 股，返回 code + name 列表。"""
    items = search_stocks(q, limit=limit)
    return {"status": "ok", "query": q, "total": len(items), "data": items}


@app.get("/api/dashboard/kline", tags=["仪表盘"])
async def dashboard_kline(
    stock_code: str = Query("600519", description="A股代码或名称，如 600519 / 贵州茅台"),
    limit: int = Query(120, ge=10, le=500),
    user: dict = Depends(require_user),
):
    """
    看板 K 线：东方财富日K OHLC，附周期统计（最高/最低/MA）。
    支持输入代码或中文名称；名称会先解析为代码。
    """
    resolved = resolve_stock_query(stock_code)
    code = resolved.get("code") or (stock_code or "").strip()
    result = fetch_kline(code, limit=limit)
    if result.get("status") == "ok":
        if not result.get("stock_name") and resolved.get("name"):
            result["stock_name"] = resolved["name"]
        if resolved.get("code"):
            result["stock_code"] = resolved["code"]
        stats = kline_period_stats(result.get("data") or [])
        result["stats"] = stats
    return result


class FeedbackRequest(BaseModel):
    category: str = "other"
    contact: str = ""
    content: str = Field(..., min_length=1)


class MultiAgentRequest(BaseModel):
    question: str
    stock_code: Optional[str] = None
    context: Optional[str] = None


class IngestReferencesRequest(BaseModel):
    paths: Optional[list[str]] = None


@app.post("/api/feedback", tags=["帮助中心"])
async def post_feedback(req: FeedbackRequest, user: dict = Depends(require_user)):
    """Persist user feedback to data/feedback.jsonl"""
    from config import DATA_DIR
    path = DATA_DIR / "feedback.jsonl"
    import json
    from datetime import datetime
    rec = {
        "username": user.get("username"),
        "role": user.get("role"),
        "category": req.category,
        "contact": req.contact,
        "content": req.content,
        "at": datetime.utcnow().isoformat() + "Z",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"status": "ok", "message": "反馈已记录"}


@app.post("/api/agent/multi", tags=["Agent"])
async def multi_agent_endpoint(req: MultiAgentRequest, user: dict = Depends(require_user)):
    """多智能体协调：分析师 → 投资者视角 → 审核 → 经理综合"""
    result = run_multi_agent(
        question=req.question,
        context=req.context or "",
        stock_code=req.stock_code or "",
    )
    return result


@app.post("/api/admin/ingest-references", tags=["系统"])
async def ingest_references(
    req: IngestReferencesRequest,
    user: dict = Depends(require_admin),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    """
    将文档资料写入知识库并建立向量索引。

    - 未指定 paths 时：默认扫描项目 data/ 目录下可导入的业务文件
      （跳过 vector_store、数据库、向量矩阵等运行时文件）
    - 指定 paths 时：支持相对项目根的路径或绝对路径
    """
    from pathlib import Path as P
    from config import BASE_DIR, DATA_DIR

    TEXT_SUFFIX = {".md", ".txt", ".csv", ".sql", ".py"}
    # 业务侧 json 可导入；运行时配置文件名见 SKIP_NAMES
    EXTRA_SUFFIX = {".json", ".pdf"}
    SKIP_DIR_NAMES = {"vector_store", "__pycache__", ".git"}
    SKIP_SUFFIX = {".db", ".npy", ".pyc", ".log", ".lock"}
    SKIP_NAMES = {
        "chunks.json", "embeddings.npy", "rag_params.json",
        "feedback.jsonl", ".gitkeep",
    }

    def _resolve(p: str) -> P:
        fp = P(p)
        if not fp.is_absolute():
            fp = (BASE_DIR / fp).resolve()
        return fp

    def _collect_data_files() -> list[str]:
        """Collect importable files under data/ (relative to project root)."""
        root = P(DATA_DIR).resolve()
        if not root.is_dir():
            return []
        found: list[str] = []
        for fp in sorted(root.rglob("*")):
            if not fp.is_file():
                continue
            # skip runtime / system dirs
            try:
                rel_parts = fp.relative_to(root).parts
            except ValueError:
                continue
            if any(part in SKIP_DIR_NAMES for part in rel_parts):
                continue
            name = fp.name
            if name in SKIP_NAMES or name.startswith("."):
                continue
            suf = fp.suffix.lower()
            if suf in SKIP_SUFFIX:
                continue
            if suf not in TEXT_SUFFIX and suf not in EXTRA_SUFFIX:
                continue
            try:
                rel = str(fp.relative_to(BASE_DIR.resolve())).replace("\\", "/")
            except ValueError:
                rel = str(fp)
            found.append(rel)
        return found

    paths = req.paths if req.paths else _collect_data_files()
    indexed = []
    errors = []
    for p in paths:
        fp = _resolve(p)
        try:
            rel = str(fp.relative_to(BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            rel = fp.name
        if not fp.exists() or not fp.is_file():
            errors.append({"path": p, "error": "文件不存在"})
            continue
        try:
            suf = fp.suffix.lower()
            if suf in TEXT_SUFFIX or suf == ".json":
                text = fp.read_text(encoding="utf-8", errors="replace")
            elif suf == ".pdf":
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(str(fp))
                    parts = []
                    for page in reader.pages[:25]:
                        try:
                            parts.append(page.extract_text() or "")
                        except Exception:
                            pass
                    text = "\n".join(parts)
                    if not text.strip():
                        errors.append({"path": p, "error": "PDF 无可提取文本"})
                        continue
                except Exception as e:
                    errors.append({"path": p, "error": f"PDF 解析失败: {e}"})
                    continue
            else:
                errors.append({"path": p, "error": f"不支持的文件类型 {suf or '(无扩展名)'}"})
                continue
            if not (text or "").strip():
                errors.append({"path": p, "error": "空文件"})
                continue
            chunks = [text[i:i + 6000] for i in range(0, min(len(text), 60000), 5500)]
            for idx, chunk in enumerate(chunks):
                title = fp.name if idx == 0 else f"{fp.name}#{idx + 1}"
                source = f"data://{rel}" if rel.startswith("data/") else f"kb://{rel}"
                res = await agent.add_to_kb(
                    title=title,
                    content=chunk,
                    doc_type="资料文档",
                    tags=["data_import", suf.lstrip(".") or "bin"],
                    related_stocks=[],
                    source_url=source,
                    file_path=rel,
                )
                indexed.append({"title": title, **res})
        except Exception as e:
            errors.append({"path": p, "error": str(e)})
    return {
        "status": "ok",
        "indexed_count": sum(1 for x in indexed if x.get("status") == "ok"),
        "scanned_files": len(paths),
        "indexed": indexed[:50],
        "errors": errors,
        "source_root": "data/",
    }


@app.post("/api/dashboard/sync", tags=["仪表盘"])
async def dashboard_sync(
    stock_code: str = Query("600519"),
    user: dict = Depends(require_admin),
):
    """管理员：按股票一键同步研报/新闻/公告/舆情真实数据入库。"""
    reports = await mcp_handler.fetch_research_reports({"stock_code": stock_code, "limit": 20})
    news = await mcp_handler.fetch_financial_news({"stock_code": stock_code, "limit": 20})
    anns = await mcp_handler.fetch_company_announcements({"stock_code": stock_code, "limit": 20})
    social = await mcp_handler.fetch_social_sentiment({"stock_code": stock_code, "limit": 30})
    kline = fetch_kline(stock_code, limit=30)
    return {
        "status": "ok",
        "stock_code": stock_code,
        "reports": {"live": reports.get("live_fetched"), "total": reports.get("total")},
        "news": {"live": news.get("live_fetched"), "total": news.get("total")},
        "announcements": {"live": anns.get("live_fetched"), "total": anns.get("total")},
        "social": {"live": social.get("live_fetched"), "total": social.get("total")},
        "kline_points": kline.get("total"),
        "sources": source_catalog(),
    }


@app.get("/api/data/sources", tags=["系统"])
async def data_sources(user: dict = Depends(require_user)):
    return {"status": "ok", "sources": source_catalog()}


@app.post("/api/admin/purge-local-paths", tags=["系统"])
async def purge_local_path_docs(
    user: dict = Depends(require_admin),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    """
    永久删除知识库中带本机绝对路径 / file:// 的文档（便于分享仓库前清理）。
    不会删除 http(s):// 与 project:// 来源。
    """
    db = SessionLocal()
    deleted = []
    try:
        docs = db.query(KnowledgeDocument).all()
        for d in docs:
            su = (d.source_url or "").strip()
            fp = (d.file_path or "").strip()
            bad = (
                su.startswith("file:")
                or "file:///" in su
                or su.startswith("C:")
                or su.startswith("/Users/")
                or "C:/Users/" in su
                or "C:\\Users\\" in su
                or (fp.startswith("C:") or fp.startswith("/Users/") or ":\\" in fp[:3])
            )
            if not bad:
                continue
            deleted.append({"id": d.id, "title": d.title, "source_url": su})
            try:
                vector_store.delete_document(str(d.id))
            except Exception:
                pass
            db.delete(d)
        db.commit()
        return {"status": "ok", "deleted_count": len(deleted), "deleted": deleted}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        db.close()


@app.post("/api/admin/purge-seed", tags=["系统"])
async def purge_seed_and_rebuild(
    stock_codes: str = Query("600519,300750,002594", description="逗号分隔股票代码"),
    user: dict = Depends(require_admin),
    agent: FinancialAnalysisAgent = Depends(get_financial_agent),
):
    """
    清除 seed:// / 本地假数据，改用真实 URL 抓取重建：
    - 删除 source_url 含 seed:// 的研报/新闻/知识库
    - 清空向量索引后用真实研报/新闻/公告写入知识库
    """
    from rag_store import vector_store
    codes = [c.strip() for c in (stock_codes or "").split(",") if c.strip()]
    db = SessionLocal()
    stats = {"deleted_reports": 0, "deleted_news": 0, "deleted_kb": 0, "indexed": 0, "synced": []}
    try:
        # 1) purge seed / non-http local rows — keep only real http(s) sources
        for r in db.query(ResearchReport).all():
            su = (r.source_url or "").strip()
            if not (su.startswith("http://") or su.startswith("https://")):
                db.delete(r)
                stats["deleted_reports"] += 1
        for n in db.query(FinancialNews).all():
            u = (n.url or "").strip()
            if not (u.startswith("http://") or u.startswith("https://")):
                db.delete(n)
                stats["deleted_news"] += 1
        # wipe entire knowledge base then rebuild from live http sources
        for d in db.query(KnowledgeDocument).all():
            try:
                vector_store.delete_document(str(d.id))
            except Exception:
                pass
            db.delete(d)
            stats["deleted_kb"] += 1
        # clear leftover seed social that looks synthetic (optional: full clear social)
        for srow in db.query(SocialSentiment).all():
            # keep after resync; clear all pre-existing then live will refill
            db.delete(srow)
        for a in db.query(CompanyAnnouncement).all():
            db.delete(a)
        db.commit()
        # empty vector store files
        try:
            vector_store.chunks = []
            vector_store.matrix = None
            vector_store._persist()
        except Exception as e:
            logger.warning("vector wipe: %s", e)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"purge failed: {e}")
    finally:
        db.close()

    # 2) live sync per stock
    for code in codes:
        reports = await mcp_handler.fetch_research_reports({"stock_code": code, "limit": 15})
        news = await mcp_handler.fetch_financial_news({"stock_code": code, "limit": 10})
        anns = await mcp_handler.fetch_company_announcements({"stock_code": code, "limit": 10})
        social = await mcp_handler.fetch_social_sentiment({"stock_code": code, "limit": 15})
        stats["synced"].append({
            "stock_code": code,
            "reports": reports.get("total"),
            "news": news.get("total"),
            "announcements": anns.get("total"),
            "social": social.get("total"),
        })

    # 3) rebuild KB from real-URL rows only
    db = SessionLocal()
    try:
        # clear any leftover vector index
        try:
            # re-index from remaining + new real reports/news
            pass
        except Exception:
            pass

        real_reports = db.query(ResearchReport).filter(
            ResearchReport.source_url.like("http%")
        ).order_by(ResearchReport.report_date.desc()).limit(40).all()
        for r in real_reports:
            content = (r.full_content or r.core_viewpoint or r.title or "").strip()
            if not content:
                continue
            # skip if already in KB with same source_url
            exists = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.source_url == r.source_url,
                KnowledgeDocument.status == "active",
            ).first()
            if exists:
                continue
            res = await agent.add_to_kb(
                title=r.title,
                content=content,
                doc_type="研报",
                tags=[r.institution or "", r.stock_code or ""],
                related_stocks=[r.stock_code] if r.stock_code else [],
                source_url=r.source_url or "",
            )
            if res.get("status") == "ok":
                stats["indexed"] += 1

        real_news = db.query(FinancialNews).filter(
            FinancialNews.url.like("http%")
        ).order_by(FinancialNews.publish_time.desc()).limit(30).all()
        for n in real_news:
            content = (n.content or n.summary or n.title or "").strip()
            if not content:
                continue
            exists = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.source_url == n.url,
                KnowledgeDocument.status == "active",
            ).first()
            if exists:
                continue
            res = await agent.add_to_kb(
                title=n.title,
                content=content,
                doc_type="新闻",
                tags=["财经新闻", n.source or ""],
                related_stocks=n.related_stocks if isinstance(n.related_stocks, list) else [],
                source_url=n.url or "",
            )
            if res.get("status") == "ok":
                stats["indexed"] += 1

        # announcements: use cninfo static url if stored in content; build from title+code
        anns = db.query(CompanyAnnouncement).order_by(
            CompanyAnnouncement.announce_date.desc()
        ).limit(20).all()
        for a in anns:
            # prefer real-looking titles only after live sync
            content = (a.content or a.summary or a.title or "").strip()
            if not content:
                continue
            # announcements table may not have source_url column; build cninfo search link
            src = f"http://www.cninfo.com.cn/new/disclosure/stock?stockCode={a.stock_code}&orgId="
            exists = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.title == a.title,
                KnowledgeDocument.doc_type == "公告",
            ).first()
            if exists:
                continue
            res = await agent.add_to_kb(
                title=a.title,
                content=content,
                doc_type="公告",
                tags=["公告", a.stock_code or ""],
                related_stocks=[a.stock_code] if a.stock_code else [],
                source_url=src,
            )
            if res.get("status") == "ok":
                stats["indexed"] += 1

        stats["kb_active"] = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.status == "active"
        ).count()
        stats["vector_chunks"] = vector_store.chunk_count
        stats["status"] = "ok"
        return stats
    finally:
        db.close()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=SERVER_CONFIG["host"], port=SERVER_CONFIG["port"], reload=SERVER_CONFIG["debug"])

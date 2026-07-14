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
)
from config import SERVER_CONFIG, UPLOAD_DIR, AUTH_CONFIG, LLM_CONFIG, OLLAMA_BASE_URL
from auth import (
    verify_password, create_token, require_user, require_admin,
    get_current_user, list_users_safe, create_user, init_default_users,
)
from rag_store import rag_params, vector_store, kb_status
from ollama_client import ollama_reachable
from seed_data import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[App] init db...")
    init_db()
    init_default_users()
    try:
        stats = seed_all(force=False, index_rag=True)
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
@app.post("/api/auth/login", tags=["认证"])
async def login(req: LoginRequest):
    user = verify_password(req.username, req.password)
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


@app.get("/api/auth/users", tags=["认证"])
async def users_list(user: dict = Depends(require_admin)):
    return {"status": "ok", "data": list_users_safe()}


@app.post("/api/auth/users", tags=["认证"])
async def users_create(req: CreateUserRequest, user: dict = Depends(require_admin)):
    try:
        created = create_user(req.username, req.password, req.role)
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
        "redis": {"ok": redis.available, "host": "localhost"},
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
    user: dict = Depends(require_user),
):
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "active")
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
                "created_at": str(d.created_at),
            } for d in docs],
        }
    finally:
        db.close()


@app.get("/api/kb/status", tags=["知识库管理"])
async def knowledge_status(user: dict = Depends(require_user)):
    return kb_status()


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
                source_url=source_url or f"file://{f.filename}",
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
    return {"status": "ok", "params": rag_params.get(), "store": {
        "document_count": vector_store.doc_count,
        "chunk_count": vector_store.chunk_count,
        "path": str(vector_store.directory),
    }}


@app.put("/api/rag/params", tags=["RAG"])
async def update_rag_params(req: RagParamsUpdate, user: dict = Depends(require_admin)):
    updated = rag_params.update(req.model_dump(exclude_none=True))
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
        }
    finally:
        db.close()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=SERVER_CONFIG["host"], port=SERVER_CONFIG["port"], reload=SERVER_CONFIG["debug"])

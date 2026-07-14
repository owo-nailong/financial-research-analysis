"""
LangChain-style financial agent with tool routing + RAG.
Falls back to direct tool orchestration when LangChain tool-calling is unavailable.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from mcp_tools import mcp_handler, MCP_TOOL_DEFINITIONS
from database import InvestmentQA, SessionLocal, KnowledgeDocument
from rag_store import vector_store, rag_params
from ollama_client import chat as ollama_chat, ollama_reachable
from config import LLM_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    history: list = field(default_factory=list)
    context: dict = field(default_factory=dict)


class RAGRetriever:
    async def retrieve(self, query: str, top_k: int = 5, doc_type: str = "全部") -> list:
        return (await mcp_handler.search_knowledge_base({
            "query": query, "top_k": top_k, "doc_type": doc_type,
        })).get("data", [])

    async def add_document(self, title: str, content: str, doc_type: str,
                           tags=None, related_stocks=None, source_url: str = "",
                           file_path: str = "") -> dict:
        db = SessionLocal()
        try:
            doc = KnowledgeDocument(
                title=title, doc_type=doc_type, content=content,
                tags=tags, related_stocks=related_stocks,
                source_url=source_url, file_path=file_path, status="active",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            try:
                if rag_params.get().get("enabled", True):
                    res = vector_store.add_document(
                        doc_id=str(doc.id), title=title, content=content,
                        source_url=source_url, file_path=file_path, doc_type=doc_type,
                        tags=tags or [], related_stocks=related_stocks or [],
                    )
                    doc.vector_id = str(doc.id)
                    db.commit()
                    return {"status": "ok", "doc_id": doc.id, "chunks": res.get("chunks", 0)}
            except Exception as e:
                logger.warning("vector index failed: %s", e)
            return {"status": "ok", "doc_id": doc.id, "chunks": 0, "warning": "vector index skipped"}
        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

    async def delete_document(self, doc_id: int) -> dict:
        db = SessionLocal()
        try:
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if not doc:
                return {"status": "error", "message": f"文档 {doc_id} 不存在"}
            doc.status = "archived"
            db.commit()
            vector_store.delete_document(str(doc_id))
            return {"status": "ok", "message": f"文档 {doc_id} 已归档"}
        finally:
            db.close()


class FinancialAnalysisAgent:
    def __init__(self, llm=None):
        self._llm = llm
        self._rag = RAGRetriever()
        self._sessions: dict[str, SessionState] = {}
        self._tools = MCP_TOOL_DEFINITIONS

    def get_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def _pick_tools(self, question: str, stock_code: Optional[str]) -> list[tuple[str, dict]]:
        """Heuristic tool routing for reliable local operation."""
        q = question or ""
        tools: list[tuple[str, dict]] = []
        code = stock_code or ""
        # extract code like 600519
        m = re.search(r"\b(\d{6})\b", q)
        if m and not code:
            code = m.group(1)

        name = ""
        for n, c in (("贵州茅台", "600519"), ("茅台", "600519"), ("宁德时代", "300750"),
                     ("宁德", "300750"), ("比亚迪", "002594")):
            if n in q:
                name = n if n != "茅台" and n != "宁德" else ("贵州茅台" if "茅" in n or n == "茅台" else "宁德时代")
                code = code or c
                break

        if any(k in q for k in ("情绪", "舆情", "市场情绪", "sentiment")):
            tools.append(("aggregate_market_sentiment", {"stock_code": code or "600519", "stock_name": name, "days": 30}))
            tools.append(("fetch_social_sentiment", {"stock_code": code or "600519", "limit": 20}))
        if any(k in q for k in ("对比", "观点", "分歧", "共识")):
            tools.append(("compare_opinions", {"stock_code": code or "600519", "stock_name": name, "limit": 10}))
        if any(k in q for k in ("评级", "目标价", "买入", "增持")):
            tools.append(("extract_investment_ratings", {"stock_code": code or "600519"}))
        if any(k in q for k in ("财务", "营收", "净利", "ROE", "eps", "EPS")):
            tools.append(("extract_financial_data", {"stock_code": code or "600519"}))
        if any(k in q for k in ("风险", "提示")):
            tools.append(("extract_risk_warnings", {"stock_code": code or "600519"}))
        if any(k in q for k in ("研报", "券商")):
            tools.append(("fetch_research_reports", {"stock_code": code or None, "stock_name": name or None, "limit": 10}))
        if any(k in q for k in ("新闻", "资讯")):
            tools.append(("fetch_financial_news", {"keyword": name or q[:20], "limit": 10}))
        if any(k in q for k in ("公告",)):
            tools.append(("fetch_company_announcements", {"stock_code": code or "600519", "limit": 10}))
        if any(k in q for k in ("摘要", "总结")):
            tools.append(("fetch_research_reports", {"stock_code": code or "600519", "limit": 3}))
        if any(k in q for k in ("预测", "盈利")):
            tools.append(("extract_profit_forecast", {"stock_code": code or "600519"}))

        if not tools:
            # default: RAG QA path + ratings if stock known
            if code:
                tools.append(("extract_investment_ratings", {"stock_code": code}))
                tools.append(("aggregate_market_sentiment", {"stock_code": code, "stock_name": name, "days": 30}))
            tools.append(("search_knowledge_base", {"query": q, "top_k": rag_params.get().get("top_k", 5)}))
        return tools[:4]

    async def chat(self, question: str, session_id: str = "default",
                   stock_code: str = None, use_rag: bool = True) -> dict:
        session = self.get_session(session_id)
        thought_chain = []
        sources = []
        tool_results = []

        selected = self._pick_tools(question, stock_code)
        for tool_name, params in selected:
            thought_chain.append({
                "type": "action", "tool": tool_name,
                "tool_input": json.dumps(params, ensure_ascii=False)[:500],
                "timestamp": datetime.utcnow().isoformat(),
            })
            result = await mcp_handler.dispatch(tool_name, params)
            tool_results.append({"tool": tool_name, "result": result})
            thought_chain.append({
                "type": "observation", "tool": tool_name,
                "output": json.dumps(result, ensure_ascii=False)[:500],
            })
            sources.append({"tool": tool_name, "summary": json.dumps(result, ensure_ascii=False)[:300]})

        rag_bits = []
        if use_rag:
            try:
                hits = await self._rag.retrieve(question, top_k=int(rag_params.get().get("top_k", 5)))
                for h in hits:
                    rag_bits.append(f"[{h.get('title')}] {h.get('content','')[:600]}")
                    sources.append({
                        "tool": "rag", "title": h.get("title"),
                        "source_url": h.get("source_url"), "score": h.get("score"),
                    })
            except Exception as e:
                logger.warning("rag retrieve: %s", e)

        context_blob = json.dumps(tool_results, ensure_ascii=False)[:12000]
        history_txt = "\n".join(
            f"{h['role']}: {h['content'][:300]}" for h in session.history[-6:]
        )
        prompt = (
            f"历史对话：\n{history_txt}\n\n"
            f"用户问题：{question}\n"
            f"关注股票：{stock_code or '未指定'}\n\n"
            f"工具结果：\n{context_blob}\n\n"
            f"RAG检索：\n{chr(10).join(rag_bits) or '无'}\n\n"
            "请综合以上信息用中文给出专业、结构化的回答，并在末尾附免责声明。"
        )
        try:
            answer = ollama_chat(
                prompt,
                system_prompt="你是智研AI金融分析助手。回答有理有据，引用工具数据。投资建议需免责声明。",
            )
        except Exception as e:
            # Compose a useful answer without LLM
            answer = self._compose_fallback(question, tool_results, rag_bits)
            answer += f"\n\n(本地模型暂不可用: {e})"

        thought_chain.append({
            "type": "finish", "output": answer[:1000],
            "timestamp": datetime.utcnow().isoformat(),
        })
        session.history.append({"role": "user", "content": question})
        session.history.append({"role": "assistant", "content": answer})

        db = SessionLocal()
        try:
            db.add(InvestmentQA(
                session_id=session_id, question=question, answer=answer,
                sources=sources, related_stocks=[stock_code] if stock_code else None,
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return {
            "answer": answer,
            "thought_chain": thought_chain,
            "sources": sources,
            "session_id": session_id,
        }

    @staticmethod
    def _compose_fallback(question: str, tool_results: list, rag_bits: list) -> str:
        lines = ["基于本地数据的分析结果：", f"问题：{question}", ""]
        for tr in tool_results:
            lines.append(f"## 工具 {tr['tool']}")
            res = tr.get("result") or {}
            if res.get("data"):
                lines.append(f"返回 {res.get('total', len(res['data']))} 条记录。")
                sample = res["data"][:3]
                for s in sample:
                    if isinstance(s, dict):
                        title = s.get("title") or s.get("content") or s.get("institution") or str(s)[:80]
                        lines.append(f"- {title}")
            elif res.get("comparison"):
                lines.append(json.dumps(res["comparison"], ensure_ascii=False, indent=2)[:800])
            elif res.get("sentiment_index"):
                lines.append(json.dumps(res["sentiment_index"], ensure_ascii=False, indent=2)[:800])
            elif res.get("rating_distribution"):
                lines.append(json.dumps(res.get("rating_distribution"), ensure_ascii=False))
            elif res.get("financial_data"):
                lines.append(json.dumps(res["financial_data"], ensure_ascii=False, indent=2)[:800])
            else:
                lines.append(json.dumps(res, ensure_ascii=False)[:500])
            lines.append("")
        if rag_bits:
            lines.append("## 知识库摘录")
            lines.extend(f"- {b[:200]}" for b in rag_bits[:3])
        lines.append("\n投资有风险，以上分析不构成投资建议，请谨慎决策。")
        return "\n".join(lines)

    async def quick_search(self, query: str, top_k: int = 5) -> dict:
        return await mcp_handler.search_knowledge_base({"query": query, "top_k": top_k})

    async def quick_summary(self, text: str, style: str = "专业") -> dict:
        return await mcp_handler.generate_summary({"text": text, "style": style})

    async def quick_sentiment(self, texts: list) -> dict:
        return await mcp_handler.analyze_sentiment({"texts": texts})

    async def quick_report(self, stock_code: str, stock_name: str = "") -> dict:
        sentiment, ratings, comparison = await asyncio.gather(
            mcp_handler.aggregate_market_sentiment({"stock_code": stock_code, "stock_name": stock_name, "days": 30}),
            mcp_handler.extract_investment_ratings({"stock_code": stock_code}),
            mcp_handler.compare_opinions({"stock_code": stock_code, "stock_name": stock_name}),
        )
        return {
            "stock_code": stock_code, "stock_name": stock_name,
            "market_sentiment": sentiment, "investment_ratings": ratings, "opinion_comparison": comparison,
        }

    async def add_to_kb(self, title: str, content: str, doc_type: str = "研报",
                        tags=None, related_stocks=None, source_url: str = "", file_path: str = "") -> dict:
        return await self._rag.add_document(
            title, content, doc_type, tags, related_stocks, source_url, file_path,
        )

    async def remove_from_kb(self, doc_id: int) -> dict:
        return await self._rag.delete_document(doc_id)

    async def search_kb(self, query: str, top_k: int = 5) -> dict:
        return await mcp_handler.search_knowledge_base({"query": query, "top_k": top_k})

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def set_focus(self, session_id: str, stocks: list):
        self.get_session(session_id).context["focus_stocks"] = stocks

    def list_tools(self) -> list:
        return [{"name": t["name"], "description": t["description"]} for t in self._tools]


_financial_agent: Optional[FinancialAnalysisAgent] = None


def get_agent() -> FinancialAnalysisAgent:
    global _financial_agent
    if _financial_agent is None:
        _financial_agent = FinancialAnalysisAgent()
    return _financial_agent

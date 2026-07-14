"""
Seed multi-source financial data and bootstrap knowledge base for RAG.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from database import (
    SessionLocal, init_db,
    ResearchReport, FinancialNews, CompanyAnnouncement, SocialSentiment,
    KnowledgeDocument, ContentTemplate,
)
from rag_store import vector_store

logger = logging.getLogger(__name__)


def _reports() -> list[dict]:
    today = date.today()
    return [
        {
            "title": "贵州茅台深度报告：品牌壁垒稳固，高端白酒龙头价值重估",
            "institution": "中信证券",
            "analyst": "李明",
            "report_date": today - timedelta(days=5),
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "report_type": "深度研究",
            "rating": "买入",
            "target_price": 1980.0,
            "current_price": 1680.0,
            "profit_forecast": {
                "2024E": {"revenue": 1680, "net_profit": 860, "eps": 68.2},
                "2025E": {"revenue": 1850, "net_profit": 960, "eps": 76.1},
            },
            "risk_warnings": "消费复苏不及预期；渠道库存波动；政策监管风险；估值回调风险。",
            "core_viewpoint": "公司直销占比提升带动毛利率改善，系列酒放量打开成长空间，维持买入评级，目标价1980元。",
            "full_content": (
                "贵州茅台2024年营业收入预计1680亿元，同比增长约15%。归母净利润预计860亿元，"
                "同比增长约16%。ROE维持在30%以上。直销渠道占比提升至45%，毛利率提升约1.2个百分点。"
                "系列酒（茅台1935等）贡献增量。给予买入评级，目标价1980元。"
                "风险提示：宏观消费疲软、批价波动、渠道政策变化。"
            ),
            "source_url": "seed://reports/citic-moutai-depth",
            "sentiment_score": 0.72,
        },
        {
            "title": "贵州茅台跟踪点评：批价企稳，旺季动销向好",
            "institution": "华泰证券",
            "analyst": "王芳",
            "report_date": today - timedelta(days=12),
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "report_type": "公司点评",
            "rating": "增持",
            "target_price": 1850.0,
            "current_price": 1680.0,
            "profit_forecast": {
                "2024E": {"revenue": 1650, "net_profit": 840, "eps": 66.5},
                "2025E": {"revenue": 1800, "net_profit": 930, "eps": 73.8},
            },
            "risk_warnings": "批价下行风险；宴席场景恢复偏慢；竞争加剧。",
            "core_viewpoint": "飞天批价企稳回升，经销商库存健康，看好旺季动销，维持增持。",
            "full_content": (
                "跟踪显示飞天茅台批价企稳，渠道库存约1个月，处于健康水平。"
                "预计2024年营收1650亿元，净利润840亿元。维持增持，目标价1850元。"
            ),
            "source_url": "seed://reports/htsc-moutai-note",
            "sentiment_score": 0.55,
        },
        {
            "title": "宁德时代：全球动力电池龙头，储能打开第二增长曲线",
            "institution": "中金公司",
            "analyst": "张伟",
            "report_date": today - timedelta(days=8),
            "stock_code": "300750",
            "stock_name": "宁德时代",
            "industry": "新能源",
            "report_type": "深度研究",
            "rating": "买入",
            "target_price": 280.0,
            "current_price": 210.0,
            "profit_forecast": {
                "2024E": {"revenue": 4200, "net_profit": 520, "eps": 11.8},
                "2025E": {"revenue": 4800, "net_profit": 610, "eps": 13.9},
            },
            "risk_warnings": "电池价格战；海外贸易壁垒；原材料价格波动；技术路线迭代。",
            "core_viewpoint": "装机量全球领先，神行/麒麟电池技术领先，储能业务高速增长，维持买入。",
            "full_content": (
                "宁德时代全球动力电池市占率约37%。2024年预计营收4200亿元，净利润520亿元。"
                "储能出货同比高增，海外本地化产能推进。买入评级，目标价280元。"
            ),
            "source_url": "seed://reports/cicc-catl",
            "sentiment_score": 0.68,
        },
        {
            "title": "比亚迪：垂直整合优势显著，出口延续高增长",
            "institution": "国泰君安",
            "analyst": "赵强",
            "report_date": today - timedelta(days=15),
            "stock_code": "002594",
            "stock_name": "比亚迪",
            "industry": "新能源汽车",
            "report_type": "深度研究",
            "rating": "增持",
            "target_price": 320.0,
            "current_price": 265.0,
            "profit_forecast": {
                "2024E": {"revenue": 7200, "net_profit": 360, "eps": 12.4},
                "2025E": {"revenue": 8500, "net_profit": 450, "eps": 15.5},
            },
            "risk_warnings": "行业价格战；出口政策风险；芯片与供应链波动。",
            "core_viewpoint": "销量与出口双轮驱动，刀片电池与e平台3.0构筑壁垒，维持增持。",
            "full_content": (
                "比亚迪新能源乘用车销量持续领先，海外市场贡献提升。"
                "垂直整合带来成本优势。给予增持评级，目标价320元。"
            ),
            "source_url": "seed://reports/gtja-byd",
            "sentiment_score": 0.6,
        },
        {
            "title": "白酒行业中性展望：分化加剧，龙头更优",
            "institution": "招商证券",
            "analyst": "陈静",
            "report_date": today - timedelta(days=20),
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "report_type": "行业研究",
            "rating": "中性",
            "target_price": 1700.0,
            "current_price": 1680.0,
            "profit_forecast": {"2024E": {"revenue": 1600, "net_profit": 820, "eps": 65.0}},
            "risk_warnings": "行业整体增速放缓；中小酒企出清；需求分层。",
            "core_viewpoint": "行业分化，推荐聚焦龙头。对茅台给予中性评级，目标价1700元。",
            "full_content": "白酒行业进入存量竞争，高端相对稳健，次高端承压。建议关注份额向龙头集中。",
            "source_url": "seed://reports/cms-liquor",
            "sentiment_score": 0.1,
        },
    ]


def _news() -> list[dict]:
    now = datetime.utcnow()
    return [
        {
            "title": "贵州茅台公告拟提升直销占比，市场解读偏积极",
            "source": "财联社",
            "author": "记者A",
            "publish_time": now - timedelta(days=2),
            "url": "seed://news/cls-moutai-direct",
            "content": "公司表示将继续优化渠道结构，直销与经销协同发展。分析认为有助于利润率提升。",
            "summary": "茅台提升直销占比，市场情绪偏积极。",
            "tags": ["白酒", "渠道"],
            "related_stocks": ["600519"],
            "sentiment_label": "positive",
            "sentiment_score": 0.65,
        },
        {
            "title": "动力电池装机数据出炉：宁德时代份额保持第一",
            "source": "证券时报",
            "author": "记者B",
            "publish_time": now - timedelta(days=3),
            "url": "seed://news/stcn-catl-share",
            "content": "最新装机数据显示宁德时代国内份额领先，储能项目中标增多。",
            "summary": "宁德时代装机份额领先，储能项目增加。",
            "tags": ["新能源", "电池"],
            "related_stocks": ["300750"],
            "sentiment_label": "positive",
            "sentiment_score": 0.58,
        },
        {
            "title": "新能源车价格战延续，板块短期承压",
            "source": "第一财经",
            "author": "记者C",
            "publish_time": now - timedelta(days=4),
            "url": "seed://news/yicai-ev-price",
            "content": "多家车企跟进降价促销，市场担忧盈利能力。龙头凭借规模与成本优势相对抗压。",
            "summary": "价格战延续，新能源板块承压。",
            "tags": ["新能源汽车", "价格战"],
            "related_stocks": ["002594", "300750"],
            "sentiment_label": "negative",
            "sentiment_score": -0.35,
        },
        {
            "title": "北向资金净流入，白酒与新能源获关注",
            "source": "新华财经",
            "author": "记者D",
            "publish_time": now - timedelta(days=1),
            "url": "seed://news/xinhua-northbound",
            "content": "北向资金连续净流入，加仓部分消费与制造龙头。",
            "summary": "北向资金流入，关注白酒与新能源龙头。",
            "tags": ["资金流向"],
            "related_stocks": ["600519", "300750"],
            "sentiment_label": "positive",
            "sentiment_score": 0.4,
        },
    ]


def _announcements() -> list[dict]:
    today = date.today()
    return [
        {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "title": "贵州茅台2024年第三季度报告",
            "announce_date": today - timedelta(days=40),
            "announce_type": "季报",
            "content": (
                "前三季度实现营业收入约1100亿元，同比增长约16%；"
                "归母净利润约560亿元，同比增长约17%。经营活动现金流稳健。"
            ),
            "summary": "茅台前三季度营收与利润双位数增长。",
            "key_points": ["营收+16%", "净利+17%", "现金流稳健"],
        },
        {
            "stock_code": "300750",
            "stock_name": "宁德时代",
            "title": "宁德时代关于投资建设海外生产基地的公告",
            "announce_date": today - timedelta(days=25),
            "announce_type": "重大事项",
            "content": "公司拟在欧洲扩大产能，服务当地车企客户，投资总额分阶段投入。",
            "summary": "宁德时代推进欧洲产能布局。",
            "key_points": ["海外扩产", "服务车企客户"],
        },
        {
            "stock_code": "002594",
            "stock_name": "比亚迪",
            "title": "比亚迪股份有限公司关于回购部分社会公众股份的公告",
            "announce_date": today - timedelta(days=18),
            "announce_type": "回购",
            "content": "拟以自有资金回购股份用于股权激励或注销，回购价格不超过董事会授权上限。",
            "summary": "比亚迪拟回购股份。",
            "key_points": ["股份回购", "股权激励"],
        },
    ]


def _social() -> list[dict]:
    now = datetime.utcnow()
    return [
        {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "platform": "雪球",
            "content": "茅台批价稳住了，长线还是看龙头，回调就是机会。",
            "author": "价值投资者A",
            "post_time": now - timedelta(hours=10),
            "sentiment_label": "positive",
            "sentiment_score": 0.7,
            "hot_index": 920,
        },
        {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "platform": "东方财富",
            "content": "估值不便宜，等财报验证动销再看。",
            "author": "股友B",
            "post_time": now - timedelta(hours=20),
            "sentiment_label": "neutral",
            "sentiment_score": 0.05,
            "hot_index": 560,
        },
        {
            "stock_code": "300750",
            "stock_name": "宁德时代",
            "platform": "同花顺",
            "content": "储能订单好看，但电池价格战让人担心利润率。",
            "author": "新能源观察",
            "post_time": now - timedelta(days=1),
            "sentiment_label": "neutral",
            "sentiment_score": -0.1,
            "hot_index": 780,
        },
        {
            "stock_code": "002594",
            "stock_name": "比亚迪",
            "platform": "微博",
            "content": "出口数据亮眼，垂直整合真的强。",
            "author": "车市点评",
            "post_time": now - timedelta(days=2),
            "sentiment_label": "positive",
            "sentiment_score": 0.62,
            "hot_index": 640,
        },
        {
            "stock_code": "300750",
            "stock_name": "宁德时代",
            "platform": "雪球",
            "content": "短期资金面承压，中长期技术与份额仍具优势。",
            "author": "制造研究员",
            "post_time": now - timedelta(hours=6),
            "sentiment_label": "positive",
            "sentiment_score": 0.35,
            "hot_index": 410,
        },
    ]


def _templates() -> list[dict]:
    return [
        {
            "name": "深度研报摘要模板",
            "category": "研报摘要",
            "prompt_template": (
                "请基于以下数据生成{stock_name}（{stock_code}）研报摘要。"
                "要求：公司概况、财务核心指标、机构评级与目标价、投资逻辑、风险提示。"
            ),
        },
        {
            "name": "投资建议书模板",
            "category": "投资建议",
            "prompt_template": (
                "请基于以下数据生成{stock_name}（{stock_code}）投资建议书。"
                "要求：投资逻辑、基本面、估值与目标价、风险收益、操作建议与免责声明。"
            ),
        },
        {
            "name": "行业分析报告模板",
            "category": "行业分析",
            "prompt_template": (
                "请生成行业分析报告。要求：行业概况、竞争格局、产业链、政策环境、机会与风险。"
            ),
        },
        {
            "name": "每日市场简报模板",
            "category": "市场简报",
            "prompt_template": (
                "请生成每日市场简报。要求：大盘综述、热点板块、资金流向、重要公告、次日关注点。"
            ),
        },
    ]


def seed_all(force: bool = False, index_rag: bool = True) -> dict:
    """Insert seed data if tables empty (or force=True). Optionally index into RAG."""
    init_db()
    db = SessionLocal()
    stats = {"reports": 0, "news": 0, "announcements": 0, "social": 0, "templates": 0, "kb": 0, "rag_chunks": 0}
    try:
        if force or db.query(ResearchReport).count() == 0:
            if force:
                db.query(ResearchReport).delete()
            for item in _reports():
                db.add(ResearchReport(**item))
                stats["reports"] += 1

        if force or db.query(FinancialNews).count() == 0:
            if force:
                db.query(FinancialNews).delete()
            for item in _news():
                db.add(FinancialNews(**item))
                stats["news"] += 1

        if force or db.query(CompanyAnnouncement).count() == 0:
            if force:
                db.query(CompanyAnnouncement).delete()
            for item in _announcements():
                db.add(CompanyAnnouncement(**item))
                stats["announcements"] += 1

        if force or db.query(SocialSentiment).count() == 0:
            if force:
                db.query(SocialSentiment).delete()
            for item in _social():
                db.add(SocialSentiment(**item))
                stats["social"] += 1

        if force or db.query(ContentTemplate).count() == 0:
            if force:
                db.query(ContentTemplate).delete()
            for item in _templates():
                db.add(ContentTemplate(**item))
                stats["templates"] += 1

        db.commit()

        # Knowledge base docs from reports for RAG
        if force or db.query(KnowledgeDocument).count() == 0:
            if force:
                for d in db.query(KnowledgeDocument).all():
                    try:
                        vector_store.delete_document(str(d.id))
                    except Exception:
                        pass
                db.query(KnowledgeDocument).delete()
                db.commit()

            reports = db.query(ResearchReport).all()
            for r in reports:
                doc = KnowledgeDocument(
                    title=r.title,
                    doc_type="研报",
                    content=r.full_content or r.core_viewpoint or "",
                    tags=[r.industry, r.institution] if r.industry else [r.institution],
                    related_stocks=[r.stock_code] if r.stock_code else [],
                    source_url=r.source_url or f"seed://report/{r.id}",
                    file_path="",
                    status="active",
                    vector_id="",
                )
                db.add(doc)
                db.flush()
                stats["kb"] += 1
                if index_rag and doc.content:
                    try:
                        res = vector_store.add_document(
                            doc_id=str(doc.id),
                            title=doc.title,
                            content=doc.content,
                            source_url=doc.source_url or "",
                            file_path=doc.file_path or "",
                            doc_type=doc.doc_type or "研报",
                            tags=doc.tags or [],
                            related_stocks=doc.related_stocks or [],
                        )
                        doc.vector_id = str(doc.id)
                        stats["rag_chunks"] += res.get("chunks", 0)
                    except Exception as e:
                        logger.warning("[Seed] RAG index failed for doc %s: %s", doc.id, e)
            db.commit()
        elif index_rag and vector_store.chunk_count == 0:
            # reindex existing KB
            docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "active").all()
            for doc in docs:
                if not doc.content:
                    continue
                try:
                    res = vector_store.add_document(
                        doc_id=str(doc.id),
                        title=doc.title,
                        content=doc.content,
                        source_url=doc.source_url or "",
                        file_path=doc.file_path or "",
                        doc_type=doc.doc_type or "自定义",
                        tags=doc.tags or [],
                        related_stocks=doc.related_stocks or [],
                    )
                    doc.vector_id = str(doc.id)
                    stats["rag_chunks"] += res.get("chunks", 0)
                except Exception as e:
                    logger.warning("[Seed] reindex failed: %s", e)
            db.commit()

        stats["ok"] = True
        stats["counts"] = {
            "reports": db.query(ResearchReport).count(),
            "news": db.query(FinancialNews).count(),
            "announcements": db.query(CompanyAnnouncement).count(),
            "social": db.query(SocialSentiment).count(),
            "kb": db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "active").count(),
            "vector_chunks": vector_store.chunk_count,
        }
        return stats
    except Exception as e:
        db.rollback()
        logger.exception("seed failed")
        return {"ok": False, "error": str(e), **stats}
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(seed_all(force=True, index_rag=True))

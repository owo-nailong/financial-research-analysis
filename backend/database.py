"""
Database layer: MySQL 8.0 (primary) + Redis cache.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Date,
    JSON, create_engine, Index, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from config import MYSQL_CONFIG, DATABASE_URL, USE_SQLITE, REDIS_CONFIG, CACHE_CONFIG

logger = logging.getLogger("database")

if USE_SQLITE:
    LongText = Text
else:
    try:
        from sqlalchemy.dialects.mysql import MEDIUMTEXT as LongText
    except Exception:
        LongText = Text

_engine_kwargs = {"echo": False}
if USE_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
    logger.info("[DB] Using SQLite: %s", DATABASE_URL)
else:
    _engine_kwargs["poolclass"] = QueuePool
    _engine_kwargs["pool_size"] = MYSQL_CONFIG["pool_size"]
    _engine_kwargs["max_overflow"] = MYSQL_CONFIG["max_overflow"]
    _engine_kwargs["pool_recycle"] = MYSQL_CONFIG["pool_recycle"]
    logger.info(
        "[DB] Using MySQL: %s:%s/%s",
        MYSQL_CONFIG["host"], MYSQL_CONFIG["port"], MYSQL_CONFIG["database"],
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_backend_name() -> str:
    if USE_SQLITE:
        return "sqlite"
    return "mysql"


def check_db_health() -> dict:
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT 1")).scalar()
            version = None
            try:
                version = conn.execute(text("SELECT VERSION()")).scalar()
            except Exception:
                pass
        return {
            "ok": True,
            "backend": db_backend_name(),
            "url_host": MYSQL_CONFIG["host"] if not USE_SQLITE else "sqlite",
            "database": MYSQL_CONFIG["database"] if not USE_SQLITE else "file",
            "version": str(version) if version else None,
            "ping": row,
        }
    except Exception as e:
        return {"ok": False, "backend": db_backend_name(), "error": str(e)}


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    institution = Column(String(128), nullable=False)
    analyst = Column(String(64))
    report_date = Column(Date, nullable=False)
    stock_code = Column(String(16))
    stock_name = Column(String(64))
    industry = Column(String(64))
    report_type = Column(String(32))
    rating = Column(String(16))
    target_price = Column(Float)
    current_price = Column(Float)
    profit_forecast = Column(JSON)
    risk_warnings = Column(Text)
    core_viewpoint = Column(Text)
    full_content = Column(LongText)
    source_url = Column(String(512))
    sentiment_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_report_stock", "stock_code", "report_date"),
        Index("idx_report_date", "report_date"),
    )


class FinancialNews(Base):
    __tablename__ = "financial_news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    source = Column(String(128), nullable=False)
    author = Column(String(64))
    publish_time = Column(DateTime, nullable=False)
    url = Column(String(512))
    content = Column(LongText)
    summary = Column(Text)
    tags = Column(JSON)
    related_stocks = Column(JSON)
    sentiment_label = Column(String(16))
    sentiment_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_news_time", "publish_time"),)


class CompanyAnnouncement(Base):
    __tablename__ = "company_announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(16), nullable=False)
    stock_name = Column(String(64))
    title = Column(String(512), nullable=False)
    announce_date = Column(Date, nullable=False)
    announce_type = Column(String(32))
    content = Column(LongText)
    summary = Column(Text)
    key_points = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_announce_stock", "stock_code", "announce_date"),)


class SocialSentiment(Base):
    __tablename__ = "social_sentiment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(16))
    stock_name = Column(String(64))
    platform = Column(String(32), nullable=False)
    content = Column(Text)
    author = Column(String(64))
    post_time = Column(DateTime, nullable=False)
    sentiment_label = Column(String(16))
    sentiment_score = Column(Float)
    hot_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_social_stock", "stock_code", "post_time"),)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), nullable=False)
    doc_type = Column(String(32))
    content = Column(LongText)
    vector_id = Column(String(128))
    tags = Column(JSON)
    related_stocks = Column(JSON)
    file_path = Column(String(512))
    source_url = Column(String(512))
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvestmentQA(Base):
    __tablename__ = "investment_qa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(LongText)
    sources = Column(JSON)
    related_stocks = Column(JSON)
    feedback = Column(String(16))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_qa_session", "session_id", "created_at"),)


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    category = Column(String(32))
    prompt_template = Column(Text)
    output_format = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemUser(Base):
    __tablename__ = "system_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(16), default="user")
    display_name = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)


class RedisCache:
    """Redis cache (graceful degrade if unavailable). Compatible with Redis 3.x."""

    _instance: Optional["RedisCache"] = None

    def __init__(self):
        self.redis = None
        self._available = False

    @classmethod
    async def get_instance(cls) -> "RedisCache":
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.connect()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    @property
    def available(self) -> bool:
        return self._available and self.redis is not None

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            if REDIS_CONFIG["password"]:
                url = (
                    f"redis://:{REDIS_CONFIG['password']}@{REDIS_CONFIG['host']}"
                    f":{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
                )
            else:
                url = f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
            self.redis = aioredis.from_url(url, decode_responses=REDIS_CONFIG["decode_responses"])
            await self.redis.ping()
            self._available = True
            logger.info("[Redis] connected")
        except Exception as e:
            self._available = False
            self.redis = None
            logger.warning("[Redis] unavailable, degrade: %s", e)

    async def get(self, key: str) -> Optional[str]:
        return await self.redis.get(key) if self.redis else None

    async def set(self, key: str, value: Any, ttl: int = None):
        if self.redis:
            ttl = ttl or CACHE_CONFIG["default_ttl"]
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            # setex works on Redis 3.x
            await self.redis.setex(key, ttl, value)

    async def delete(self, key: str):
        if self.redis:
            await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) > 0 if self.redis else False

    @staticmethod
    def build_key(prefix: str, *args) -> str:
        return ":".join([prefix] + [str(a) for a in args])


def init_db():
    Base.metadata.create_all(bind=engine)
    # ensure source_url column exists on knowledge_documents for older DBs
    if not USE_SQLITE:
        try:
            with engine.connect() as conn:
                cols = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA=:db AND TABLE_NAME='knowledge_documents'"
                ), {"db": MYSQL_CONFIG["database"]}).fetchall()
                names = {r[0] for r in cols}
                if "source_url" not in names:
                    conn.execute(text(
                        "ALTER TABLE knowledge_documents ADD COLUMN source_url VARCHAR(512) NULL"
                    ))
                    conn.commit()
        except Exception as e:
            logger.warning("[DB] migrate source_url: %s", e)

"""Pydantic request/response models."""
from typing import Optional, Any
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    status: str = "ok"
    message: str = ""
    data: Any = None


class LoginRequest(BaseModel):
    username: str
    # Legacy plaintext is rejected by the API; only encrypted form is accepted.
    password: Optional[str] = None
    password_encrypted: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password_encrypted: str
    new_password_encrypted: str


class AdminSetPasswordRequest(BaseModel):
    username: str
    new_password_encrypted: str


class FetchReportsRequest(BaseModel):
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    industry: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class FetchNewsRequest(BaseModel):
    keyword: Optional[str] = None
    stock_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sentiment: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class FetchAnnouncementsRequest(BaseModel):
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    announce_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class FetchSocialRequest(BaseModel):
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    platform: str = "全部"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)


class ExtractFinancialRequest(BaseModel):
    text: Optional[str] = None
    stock_code: Optional[str] = None
    report_id: Optional[int] = None


class ExtractForecastRequest(BaseModel):
    stock_code: str
    report_ids: Optional[list[int]] = None


class ExtractRatingsRequest(BaseModel):
    stock_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ExtractRiskRequest(BaseModel):
    stock_code: str
    report_ids: Optional[list[int]] = None


class CompareOpinionsRequest(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=10)


class SentimentRequest(BaseModel):
    texts: list[str]
    context: Optional[str] = None


class MarketSentimentRequest(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    days: int = Field(default=30, ge=1, le=365)


class SummaryRequest(BaseModel):
    text: str
    doc_type: str = "自动"
    style: str = "专业"
    max_length: int = Field(default=500, ge=50, le=2000)


class InvestmentQARequest(BaseModel):
    question: str
    session_id: str = "default"
    stock_code: Optional[str] = None
    use_rag: bool = True


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: str = "全部"
    stock_code: Optional[str] = None


class ContentGenerateRequest(BaseModel):
    content_type: str = "研报摘要"
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    template_id: Optional[int] = None
    extra_params: Optional[dict] = None


class PortfolioAnalysisRequest(BaseModel):
    stocks: list[dict]
    days: int = Field(default=30, ge=1, le=365)


class AgentChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    stock_code: Optional[str] = None
    use_rag: bool = True


class AgentChatResponse(BaseModel):
    answer: str
    thought_chain: list[dict] = []
    sources: list[dict] = []
    session_id: str = ""


class KnowledgeAddRequest(BaseModel):
    title: str
    content: str
    doc_type: str = "自定义"
    tags: Optional[list[str]] = None
    related_stocks: Optional[list[str]] = None
    source_url: Optional[str] = None


class KnowledgeDeleteRequest(BaseModel):
    doc_id: int


class KnowledgeListRequest(BaseModel):
    doc_type: Optional[str] = None
    page: int = 1
    page_size: int = 20


class TemplateCreateRequest(BaseModel):
    name: str
    category: str = "自定义"
    prompt_template: str
    output_format: Optional[dict] = None


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    prompt_template: Optional[str] = None
    output_format: Optional[dict] = None


class RagParamsUpdate(BaseModel):
    enabled: Optional[bool] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    chunk_size: Optional[int] = Field(default=None, ge=100, le=4000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=1000)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    embedding_model: Optional[str] = None
    # fixed | sentence | paragraph | markdown | custom
    chunk_strategy: Optional[str] = None
    # custom strategy: regex separator (e.g. \\n\\n+ or \\|\\|\\|)
    chunk_separator: Optional[str] = None


class CreateUserRequest(BaseModel):
    username: str
    password: Optional[str] = None
    password_encrypted: Optional[str] = None
    role: str = "user"
    display_name: Optional[str] = None

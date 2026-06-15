from pydantic import BaseModel, Field
from typing import Optional, List


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    ticker: Optional[str] = Field(None, description="Hisse kodu filtresi (orn: THYAO)")
    top_k: int = Field(3, ge=1, le=10)
    llm_provider: Optional[str] = Field(None, description="ollama veya claude")
    include_contexts: bool = Field(False, description="RAGAS evaluation icin context metinleri dondur")


class SourceRef(BaseModel):
    label: str
    ticker: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceRef]
    latency_ms: float
    rejected: bool = False
    contexts: List[str] = Field(default_factory=list, description="Retrieval edilmis context metinleri (RAGAS icin)")


class HealthResponse(BaseModel):
    status: str
    chroma: bool
    ollama: bool


class StatsResponse(BaseModel):
    total_documents: int
    collection: str


class IngestRequest(BaseModel):
    tickers: List[str] = Field(..., description="Hisse kodu listesi")
    days_back: int = Field(365, ge=1, le=1825)
    kap_only: bool = False
    yf_only: bool = False
    no_pdf: bool = False
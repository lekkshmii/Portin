from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# --- Deep Research Models ---

class Citation(BaseModel):
    """A specific source citation for a claim."""
    source_url: str
    source_title: Optional[str] = None
    snippet: Optional[str] = None
    credibility_score: float = 0.0  # 0.0 to 1.0
    access_date: str = Field(default_factory=lambda: datetime.now().isoformat())

class VerifiedClaim(BaseModel):
    """A single verified fact with supporting evidence."""
    claim_text: str
    confidence_score: float = 0.0  # 0.0 to 1.0
    verification_status: str = "unverified"  # verified, disputed, unverified
    citations: List[Citation] = Field(default_factory=list)
    source_field: Optional[str] = None  # e.g., "revenue", "employee_count"

class ResearchQuestion(BaseModel):
    """A question generated to fill a data gap."""
    question: str
    priority: str = "medium"  # high, medium, low
    rationale: Optional[str] = None
    status: str = "pending"  # pending, answered, failed
    answer: Optional[str] = None
    
class DeepResearchMetadata(BaseModel):
    """Metadata about the research process itself."""
    research_grade: str = "N/A"  # A, B, C, D, F
    hallucination_risk_score: float = 0.0  # 0.0 to 100.0 (Lower is better)
    research_completed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    sources_consulted: int = 0
    claims_verified: int = 0

# --- Existing Models (re-export or extend if necessary) ---
# Note: In a real refactor we might merge these, but appending avoids breaking imports.

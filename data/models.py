"""
Pydantic Models for Portin

Data validation for:
- Search criteria
- Discovered companies
- Enriched company data

All data passes through these models for validation.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, HttpUrl
import re


# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class CompanyStatus(str, Enum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    FAILED = "failed"
    SKIPPED = "skipped"


class Priority(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COOL = "COOL"
    COLD = "COLD"


class OwnershipType(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    FAMILY = "family"
    PE_BACKED = "PE-backed"
    VC_BACKED = "VC-backed"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────
# SEARCH CRITERIA
# ─────────────────────────────────────────────────────────────

class IndustryCriteria(BaseModel):
    """Industry targeting criteria."""
    industry: List[str] = Field(default_factory=list, description="Target industries")
    keywords: List[str] = Field(default_factory=list, description="Search keywords")
    sic_codes: List[str] = Field(default_factory=list, description="SIC codes")
    specifics: Optional[str] = None


class RevenueCriteria(BaseModel):
    """Revenue range criteria."""
    min_revenue_millions: Optional[float] = None
    max_revenue_millions: Optional[float] = None
    currency: str = "USD"
    no_preference: bool = False


class GeographyCriteria(BaseModel):
    """Geographic targeting."""
    countries: List[str] = Field(default_factory=list, description="ISO country codes")
    regions: List[str] = Field(default_factory=list, description="Region names")
    include_global: bool = False


class OwnershipCriteria(BaseModel):
    """Ownership type preferences."""
    types: List[str] = Field(default_factory=list)
    no_preference: bool = True


class CapabilitiesCriteria(BaseModel):
    """Required capabilities/synergies."""
    must_have: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)
    no_preference: bool = True


class SearchCriteria(BaseModel):
    """Complete search criteria for M&A target discovery."""
    reference_companies: List[str] = Field(default_factory=list)
    industry: IndustryCriteria = Field(default_factory=IndustryCriteria)
    revenue: RevenueCriteria = Field(default_factory=RevenueCriteria)
    geography: GeographyCriteria = Field(default_factory=GeographyCriteria)
    ownership: OwnershipCriteria = Field(default_factory=OwnershipCriteria)
    capabilities: CapabilitiesCriteria = Field(default_factory=CapabilitiesCriteria)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SearchCriteria":
        """Create from dictionary (for backward compatibility with JSON)."""
        return cls(**data)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return self.model_dump()


# ─────────────────────────────────────────────────────────────
# DISCOVERED COMPANY
# ─────────────────────────────────────────────────────────────

class DiscoveredCompany(BaseModel):
    """A company found during discovery."""
    name: str = Field(..., min_length=1)
    domain: Optional[str] = None
    website: Optional[str] = None
    source: str = "unknown"
    source_url: Optional[str] = None
    info: Optional[str] = None
    location: Optional[str] = None
    
    @field_validator('name')
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Clean company name."""
        # Remove extra whitespace
        v = ' '.join(v.split())
        # Remove common suffixes if they're the entire name
        if v.lower() in ['inc', 'llc', 'ltd', 'corp', 'company']:
            raise ValueError("Name cannot be just a suffix")
        return v
    
    @field_validator('domain')
    @classmethod  
    def clean_domain(cls, v: Optional[str]) -> Optional[str]:
        """Clean domain."""
        if v:
            v = v.lower().strip()
            v = v.replace('www.', '')
            v = re.sub(r'^https?://', '', v)
            v = v.split('/')[0]  # Remove path
        return v


# ─────────────────────────────────────────────────────────────
# ENRICHED COMPANY DATA
# ─────────────────────────────────────────────────────────────


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

class EnrichedCompany(BaseModel):
    """Fully enriched company data for Excel export."""
    
    # Core identifiers
    company_name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    
    # Business info
    company_description: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None  # B2B, B2C, Both
    products_services: Optional[str] = None
    
    # Financials
    revenue_estimate: Optional[str] = None
    revenue_source: Optional[str] = None  # "10-K verified", "estimated", etc.
    employee_count: Optional[str] = None
    company_size: Optional[str] = None  # Startup, SMB, Mid-Market, Enterprise
    
    # Location
    headquarters: Optional[str] = None
    geographic_reach: Optional[str] = None
    
    # Ownership
    ownership_type: Optional[str] = None
    parent_company: Optional[str] = None
    key_executives: Optional[str] = None
    
    # M&A relevance
    ma_fit_score: Optional[float] = Field(None, ge=0, le=100)
    acquisition_rationale: Optional[str] = None
    strategic_value: Optional[str] = None
    potential_concerns: Optional[str] = None
    
    # Source tracking
    data_sources: List[str] = Field(default_factory=list)
    confidence_level: Optional[str] = None  # High, Medium, Low
    
    # Metadata
    source: str = "Portin AI_v1"
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    priority: Optional[Priority] = None
    status: CompanyStatus = CompanyStatus.ENRICHED
    enriched_at: Optional[datetime] = None
    
    # Deep Research & Evidence
    research_metadata: Optional[DeepResearchMetadata] = None
    verified_claims: List[VerifiedClaim] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    
    # Apollo.io Data
    apollo_data: Optional[Dict[str, Any]] = None # Raw verified data from Apollo
    
    # Regulatory IDs (Phase 2+)
    sec_cik: Optional[str] = None
    sic_code: Optional[str] = None
    companies_house_number: Optional[str] = None
    
    def to_excel_row(self) -> Dict[str, Any]:
        """Convert to row for Excel export."""
        return {
            "Company Name": self.company_name,
            "Website": self.website,
            "Description": self.company_description,
            "Industry": self.industry,
            "Business Model": self.business_model,
            "Products/Services": self.products_services,
            "Revenue": self.revenue_estimate,
            "Employees": self.employee_count,
            "Size": self.company_size,
            "HQ": self.headquarters,
            "Reach": self.geographic_reach,
            "Ownership": self.ownership_type,
            "Parent": self.parent_company,
            "Executives": self.key_executives,
            "M&A Score": self.ma_fit_score,
            "Rationale": self.acquisition_rationale,
            "Strategic Value": self.strategic_value,
            "Concerns": self.potential_concerns,
            "Priority": self.priority.value if self.priority else None,
        }


# ─────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────

class Session(BaseModel):
    """A discovery/enrichment session."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    status: str = "active"
    criteria: SearchCriteria = Field(default_factory=SearchCriteria)
    config: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def validate_company(data: Dict) -> Optional[DiscoveredCompany]:
    """Validate company data, return None if invalid."""
    try:
        return DiscoveredCompany(**data)
    except Exception:
        return None


def validate_enriched_company(data: Dict) -> Optional[EnrichedCompany]:
    """Validate enriched company data, return None if invalid."""
    try:
        return EnrichedCompany(**data)
    except Exception:
        return None

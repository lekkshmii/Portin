"""
Deep Research Engine for M&A Integration
Implements the 6-stage anti-hallucination pipeline + Apollo.io Verification.
"""

import os
import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import google.generativeai as genai
from pydantic import ValidationError

from data.models import (
    EnrichedCompany, VerifiedClaim, Citation, 
    DeepResearchMetadata, ResearchQuestion, Priority, CompanyStatus
)
from sources.google_grounding import GoogleGroundingSearch
from sources.crawl4ai_scraper import scrape_url
from sources.sec_edgar import get_company_financials
from config.model_config import get_current_model

class DeepResearchEnricher:
    """
    Orchestrates the Deep Research pipeline:
    1. Apollo.io Check (Verified Data)
    2. Query Decomposition (Hypothesis Generation)
    3. Parallel Retrieval (Broad Search)
    4. Conflict Detection & Gap Analysis
    5. Consensus Extraction (Fact verification)
    6. Final Scoring & Risk Assessment
    """
    
    def __init__(self):
        self.gemini = genai.GenerativeModel(get_current_model())
        self.grounding = GoogleGroundingSearch()
        self.apollo_key = os.getenv('APOLLO_API_KEY')
        self.serper_key = os.getenv('SERPER_KEY')
        
        # System instructions for Research Agent
        self.research_sys_prompt = """
        You are an elite M&A Research Analyst. 
        Your goal is to extract strictly verified facts about companies.
        NEVER guess. If data is conflicting, verify with citations.
        """
        
        # Track Gemini calls made by this enricher
        self.gemini_call_count = 0

    def get_stats(self):
        """Return call stats from this enricher."""
        return {
            'grounding_calls': self.grounding.call_count if self.grounding else 0,
            'gemini_calls': self.gemini_call_count
        }

    def enrich_company(self, company_name: str, domain: str = None, website: str = None, initial_context: str = "") -> EnrichedCompany:
        """Main entry point for Deep Research."""
        print(f"\n🔬 Deep Research: {company_name}")
        
        start_time = time.time()
        
        # Initialize empty result
        result = EnrichedCompany(
            company_name=company_name, 
            domain=domain, 
            website=website,
            research_metadata=DeepResearchMetadata()
        )
        
        # Ingest initial context (e.g. from homepage scrape)
        if initial_context:
            print(f"   [Context] Ingested {len(initial_context)} chars of initial context")
            # We treat this as the first piece of evidence
            # This allows the rest of the pipeline to see it
            # For now, we'll append it to the consensus prompt later
            pass

        # Stage 1: Apollo.io Verification (The "Truth" Layer)
        apollo_data = self._check_apollo(domain or company_name)
        if apollo_data:
            print(f"   [Apollo] Found verified data")
            result.apollo_data = apollo_data
            # Merge safe Apollo fields into result
            self._merge_apollo_data(result, apollo_data)
        
        # Stage 2: Decomposition & Hypothesis
        # We assume gaps unless Apollo gave us everything (it rarely does for private M&A fit)
        questions = self._decompose_query(result)
        
        if not questions:
            print("   [Skip] Data sufficient, skipping deep web crawl.")
            result.status = CompanyStatus.ENRICHED
            return result

        # Stage 3: Parallel Retrieval
        print(f"   [Deep Search] Investigating {len(questions)} strategic questions...")
        evidence = self._parallel_retrieve(company_name, questions)
        
        # Stage 4 & 5: Conflict Resolution & Consensus
        print(f"   [Analysis] Synthesizing {len(evidence)} evidence points...")
        consensus = self._extract_consensus(company_name, evidence, result, initial_context)
        
        # Stage 6: Final Merge & Validation
        final_result = self._finalize_research(result, consensus)
        
        duration = time.time() - start_time
        print(f"   [Done] Research complete in {duration:.1f}s. Grade: {final_result.research_metadata.research_grade}")
        
        return final_result

    def _check_apollo(self, query: str) -> Optional[Dict]:
        """
        Check Apollo.io for verified firmographics.
        Uses Organization Enrichment API.
        
        Args:
            query: Domain (preferred) or Company Name
        """
        if not self.apollo_key:
            # Try alternate key
             self.apollo_key = os.getenv('APOLLO_API_KEY')
             
        if not self.apollo_key:
            return None

        # Clean domain if possible
        domain = query
        if "http" in query or "www" in query:
             # Basic extraction, assumes query might be a url
             import re
             domain = re.sub(r'^https?://', '', query)
             domain = domain.replace('www.', '').split('/')[0]

        url = "https://api.apollo.io/api/v1/organizations/bulk_enrich"
        
        # Safe Mode: Only run if explicitly allowed or low volume
        # We assume this is run one-by-one so it's 1 credit per call.
        
        payload = {
            "api_key": self.apollo_key,
            "domains": [domain]
        }

        try:
            print(f"   [Apollo] Verifying {domain}...")
            # Using requests directly instead of self.grounding (which is Google)
            import requests
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('organizations', [])
                if matches and matches[0]:
                    org = matches[0]
                    # Check if it's a real match
                    if org.get('name'):
                        return org
            else:
                # 404 or other error means no data found
                pass
                
        except Exception as e:
            print(f"   [Apollo] Lookup failed: {e}")
            
        return None

    def _merge_apollo_data(self, company: EnrichedCompany, apollo_data: Dict):
        """Merge Apollo data into member fields."""
        # TODO: Map Apollo JSON to EnrichedCompany fields
        pass

    def _decompose_query(self, current_state: EnrichedCompany) -> List[ResearchQuestion]:
        """Generate research questions based on missing critical data."""
        questions = []
        
        # Always verify revenue if missing or unverified
        if not current_state.revenue_estimate or current_state.revenue_source == "estimated":
             questions.append(ResearchQuestion(question=f"What is the annual revenue of {current_state.company_name}?", priority="high"))
        
        # Deep M&A drivers
        questions.append(ResearchQuestion(question=f"Who are the key customers and strategic partners of {current_state.company_name}?", priority="medium"))
        questions.append(ResearchQuestion(question=f"What are the specific manufacturing capabilities of {current_state.company_name}?", priority="medium"))
        
        return questions

    def _parallel_retrieve(self, company_name: str, questions: List[ResearchQuestion]) -> List[Dict]:
        """
        Execute searches for each question.
        Returns raw text chunks with source metadata.
        """
        evidence_chunks = []
        
        # Simply use Google Grounding + Scraper for now (can expand to SEC/News later)
        # We can optimize this to be truly parallel with asyncio later
        for q in questions:
            print(f"      -> Searching: {q.question}")
            # 1. Search
            results = self.grounding.search(f"{company_name} {q.question}")
            
            # 2. Extract context
            if results:
                evidence_chunks.append({
                     "source": "google_grounding",
                     "content": results, # Grounding returns a string summary usually
                     "query": q.question
                })
                
        return evidence_chunks

    def _extract_consensus(self, company_name: str, evidence: List[Dict], current_state: EnrichedCompany, initial_context: str = "") -> Dict:
        """
        Uses Gemini to read all evidence and formulate verified claims with citations.
        """
        context_block = "\n\n".join([f"Source ({e['source']}): {e['content']}" for e in evidence])
        
        # Add initial context
        if initial_context:
            context_block = f"HOMEPAGE SCRAPE:\n{initial_context[:20000]}\n\n" + context_block
        
        prompt = f"""
        Analyze the following research on '{company_name}' and produce a Verified M&A Profile.
        
        EVIDENTIARY CONTEXT:
        {context_block[:50000]} # Large context window usage
        
        TASK:
        1. Extract exact revenue figures (with year).
        2. Identify specific products and manufacturing capabilities.
        3. Flag any contradictions (e.g. source A says $5M, source B says $50M).
        4. Assign a confidence score (0.0-1.0) for each fact.
        
        Return JSON matching the VerifiedClaim and EnrichedCompany structure.
        """
        
        # Stub for Gemini call
        # response = self.gemini.generate_content(prompt)
        # parsed = json.loads(response.text)
        
        # Returning mock consensus for initial compilation check
        return {
            "revenue": {"amount": "$10M-50M", "confidence": 0.8},
            "claims": []
        }

    def _finalize_research(self, company: EnrichedCompany, consensus: Dict) -> EnrichedCompany:
        """Merge consensus data back into the main object."""
        
        # Mock update
        company.research_metadata.research_completed_at = datetime.now().isoformat()
        company.research_metadata.research_grade = "B" # Placeholder
        
        return company

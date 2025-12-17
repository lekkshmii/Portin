"""
OpenCorporates API Module for Portin

Search global company registry data:
- Search companies worldwide by name/keyword
- Free tier: 500 requests/month (no API key)
- Get company details, jurisdiction, officers

Usage:
    from opencorporates import OpenCorporatesSearch
    
    oc = OpenCorporatesSearch()
    companies = oc.search("packaging", jurisdiction="us")
"""

import requests
import os
from typing import List, Dict, Optional
from utils.logging import get_logger
from utils.retry import retry_api_call

logger = get_logger(__name__)

# OpenCorporates API base URL
OC_API_URL = "https://api.opencorporates.com/v0.4"


class OpenCorporatesSearch:
    """
    Search global company data via OpenCorporates API.
    Free tier: 500 requests/month (no key needed).
    """
    
    def __init__(self, api_token: str = None):
        # API token is optional - free tier works without it
        self.api_token = api_token or os.getenv("OPENCORPORATES_API_TOKEN")
    
    def _get_params(self, **kwargs) -> Dict:
        """Build params with optional API token."""
        params = dict(kwargs)
        if self.api_token:
            params["api_token"] = self.api_token
        return params
    
    @retry_api_call(max_attempts=3, min_wait=1, max_wait=10)
    def search(
        self, 
        query: str, 
        jurisdiction: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search for companies globally.
        
        Args:
            query: Company name or keyword
            jurisdiction: Optional jurisdiction code (e.g., "us_ca", "gb", "de")
            limit: Maximum results (free tier limited)
            
        Returns:
            List of company dicts
        """
        logger.info("Searching OpenCorporates", query=query, jurisdiction=jurisdiction)
        
        url = f"{OC_API_URL}/companies/search"
        
        params = self._get_params(
            q=query,
            per_page=min(limit, 30)  # Free tier limited
        )
        
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            companies = data.get("results", {}).get("companies", [])
            
            results = []
            for item in companies:
                company = item.get("company", {})
                results.append({
                    "name": company.get("name", ""),
                    "company_number": company.get("company_number", ""),
                    "jurisdiction": company.get("jurisdiction_code", ""),
                    "status": company.get("current_status", ""),
                    "type": company.get("company_type", ""),
                    "address": company.get("registered_address_in_full", ""),
                    "incorporated_date": company.get("incorporation_date", ""),
                    "opencorporates_url": company.get("opencorporates_url", ""),
                    "source": "opencorporates"
                })
            
            logger.info("Search complete", query=query, found=len(results))
            return results
        
        elif response.status_code == 401:
            logger.warning("OpenCorporates API token invalid or quota exceeded")
        else:
            logger.error("OpenCorporates API error", status=response.status_code)
        
        return []
    
    @retry_api_call(max_attempts=3, min_wait=1, max_wait=10)
    def get_company(self, jurisdiction: str, company_number: str) -> Optional[Dict]:
        """
        Get full company details.
        
        Args:
            jurisdiction: Jurisdiction code (e.g., "us_ca", "gb")
            company_number: Company registration number
            
        Returns:
            Full company details or None
        """
        url = f"{OC_API_URL}/companies/{jurisdiction}/{company_number}"
        
        params = self._get_params()
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            company = data.get("results", {}).get("company", {})
            
            return {
                "name": company.get("name", ""),
                "company_number": company.get("company_number", ""),
                "jurisdiction": company.get("jurisdiction_code", ""),
                "status": company.get("current_status", ""),
                "type": company.get("company_type", ""),
                "address": company.get("registered_address_in_full", ""),
                "incorporated_date": company.get("incorporation_date", ""),
                "dissolved_date": company.get("dissolution_date", ""),
                "industry_codes": company.get("industry_codes", []),
                "agents": [a.get("agent", {}).get("name") for a in company.get("agent_name", [])],
                "officers": self._extract_officers(company.get("officers", [])),
                "opencorporates_url": company.get("opencorporates_url", ""),
                "source": "opencorporates"
            }
        
        return None
    
    def _extract_officers(self, officers: List[Dict]) -> List[str]:
        """Extract officer names from officers list."""
        names = []
        for officer_entry in officers[:5]:  # Limit to 5
            officer = officer_entry.get("officer", {})
            name = officer.get("name", "")
            position = officer.get("position", "")
            if name:
                names.append(f"{name} ({position})" if position else name)
        return names
    
    def search_us_companies(self, query: str, limit: int = 20) -> List[Dict]:
        """Search US companies only."""
        # US has multiple jurisdictions (us_ca, us_ny, us_de, etc.)
        # Search without jurisdiction to get all US results
        results = self.search(query, limit=limit)
        
        # Filter to US jurisdictions
        us_results = [r for r in results if r.get("jurisdiction", "").startswith("us_")]
        return us_results
    
    def search_uk_companies(self, query: str, limit: int = 20) -> List[Dict]:
        """Search UK companies only."""
        return self.search(query, jurisdiction="gb", limit=limit)


# Jurisdiction codes for common countries
JURISDICTIONS = {
    "US": ["us_ca", "us_ny", "us_de", "us_tx", "us_fl", "us_il"],
    "UK": ["gb"],
    "Germany": ["de"],
    "France": ["fr"],
    "Canada": ["ca"],
    "Australia": ["au"],
}


# Singleton instance
_oc_search = None

def get_opencorporates_search() -> OpenCorporatesSearch:
    """Get singleton OpenCorporates search instance."""
    global _oc_search
    if _oc_search is None:
        _oc_search = OpenCorporatesSearch()
    return _oc_search

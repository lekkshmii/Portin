"""
UK Companies House API Module for Portin

Search UK companies via Companies House API:
- Search by company name/keyword
- Get company profile (SIC codes, addresses, officers)
- FREE but requires API key from:
  https://developer.company-information.service.gov.uk/

Note: Cannot search BY SIC code directly - search by name, then filter.

Usage:
    from companies_house import CompaniesHouseSearch
    
    ch = CompaniesHouseSearch(api_key="your_api_key")
    companies = ch.search("packaging")
"""

import requests
import os
import base64
from typing import List, Dict, Optional
from utils.logging import get_logger
from utils.retry import retry_api_call

logger = get_logger(__name__)

# Companies House API base URL
CH_API_URL = "https://api.company-information.service.gov.uk"


class CompaniesHouseSearch:
    """
    Search UK companies via Companies House API.
    Requires free API key from developer portal.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("COMPANIES_HOUSE_API_KEY")
        
        if not self.api_key:
            logger.warning("COMPANIES_HOUSE_API_KEY not set")
        
        # API uses Basic Auth with API key as username, empty password
        self.headers = {
            "Authorization": f"Basic {self._encode_key()}"
        } if self.api_key else {}
    
    def _encode_key(self) -> str:
        """Encode API key for Basic Auth."""
        if not self.api_key:
            return ""
        # API key is username, password is empty
        credentials = f"{self.api_key}:"
        return base64.b64encode(credentials.encode()).decode()
    
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
    
    @retry_api_call(max_attempts=3, min_wait=1, max_wait=10)
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for companies by name/keyword.
        
        Args:
            query: Company name or keyword
            limit: Maximum results (max 100)
            
        Returns:
            List of company dicts
        """
        if not self.api_key:
            logger.warning("Companies House API key not configured")
            return []
        
        logger.info("Searching Companies House", query=query)
        
        url = f"{CH_API_URL}/search/companies"
        params = {
            "q": query,
            "items_per_page": min(limit, 100)
        }
        
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "name": item.get("title", ""),
                    "company_number": item.get("company_number", ""),
                    "status": item.get("company_status", ""),
                    "type": item.get("company_type", ""),
                    "address": self._format_address(item.get("address", {})),
                    "date_created": item.get("date_of_creation", ""),
                    "source": "companies_house"
                })
            
            logger.info("Search complete", query=query, found=len(results))
            return results
        
        elif response.status_code == 401:
            logger.error("Companies House API key invalid")
        else:
            logger.error("Companies House API error", status=response.status_code)
        
        return []
    
    @retry_api_call(max_attempts=3, min_wait=1, max_wait=10)
    def get_company(self, company_number: str) -> Optional[Dict]:
        """
        Get full company profile.
        
        Args:
            company_number: UK company number (e.g., "12345678")
            
        Returns:
            Full company profile or None
        """
        if not self.api_key:
            return None
        
        url = f"{CH_API_URL}/company/{company_number}"
        
        response = requests.get(url, headers=self.headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            return {
                "name": data.get("company_name", ""),
                "company_number": data.get("company_number", ""),
                "status": data.get("company_status", ""),
                "type": data.get("type", ""),
                "sic_codes": data.get("sic_codes", []),
                "address": self._format_address(data.get("registered_office_address", {})),
                "date_created": data.get("date_of_creation", ""),
                "accounts_next_due": data.get("accounts", {}).get("next_due", ""),
                "confirmation_next_due": data.get("confirmation_statement", {}).get("next_due", ""),
                "source": "companies_house"
            }
        
        return None
    
    def search_and_enrich(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for companies and get full profiles with SIC codes.
        
        Args:
            query: Search term
            limit: Max results
            
        Returns:
            List of enriched company profiles
        """
        companies = self.search(query, limit=limit)
        
        enriched = []
        for company in companies:
            company_number = company.get("company_number")
            if company_number:
                profile = self.get_company(company_number)
                if profile:
                    enriched.append(profile)
        
        return enriched
    
    def _format_address(self, address: Dict) -> str:
        """Format address dict as string."""
        parts = []
        for key in ["premises", "address_line_1", "address_line_2", "locality", "region", "postal_code", "country"]:
            if address.get(key):
                parts.append(address[key])
        return ", ".join(parts)


# UK-specific SIC codes (subset relevant to M&A)
UK_SIC_CODES = {
    # Manufacturing
    "17120": "Manufacture of paper and paperboard",
    "17210": "Manufacture of corrugated paper and paperboard",
    "17220": "Manufacture of household and sanitary goods",
    "17230": "Manufacture of paper stationery",
    "17290": "Manufacture of other paper products",
    "18120": "Printing",
    "18130": "Pre-press and pre-media services",
    "22220": "Manufacture of plastic packing goods",
    
    # Food
    "10110": "Processing and preserving of meat",
    "10510": "Operation of dairies and cheese making",
    "10520": "Manufacture of ice cream",
    "10710": "Manufacture of bread",
    "10820": "Manufacture of cocoa, chocolate",
    "11010": "Distilling, rectifying spirits",
    "11050": "Manufacture of beer",
}


def filter_by_sic(companies: List[Dict], sic_codes: List[str]) -> List[Dict]:
    """
    Filter company list to those with matching SIC codes.
    
    Args:
        companies: List of enriched company profiles
        sic_codes: List of SIC codes to match
        
    Returns:
        Filtered list
    """
    filtered = []
    for company in companies:
        company_sics = company.get("sic_codes", [])
        if any(sic in company_sics for sic in sic_codes):
            filtered.append(company)
    return filtered


# Singleton instance
_ch_search = None

def get_companies_house_search() -> CompaniesHouseSearch:
    """Get singleton Companies House search instance."""
    global _ch_search
    if _ch_search is None:
        _ch_search = CompaniesHouseSearch()
    return _ch_search

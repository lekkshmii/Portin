"""
SEC EDGAR Search Module for Portin (OPTIMIZED)

Fast search for US public companies using bulk data files.
No individual API calls - filters locally for speed.

Uses:
- company_tickers_exchange.json - Has SIC codes built-in
- Gemini for smart relevance filtering
- Local caching for instant repeated searches

FREE - No API key required.

Usage:
    from sources.sec_edgar import SECEdgarSearch
    
    sec = SECEdgarSearch()
    companies = sec.search_by_sic("2650")  # Paperboard Containers
    companies = sec.search_by_keywords(["packaging", "printing"])
"""

import os
import json
import requests
from typing import List, Dict, Optional
from utils.logging import get_logger
from utils.retry import retry_api_call

logger = get_logger(__name__)

# SEC EDGAR URLs
SEC_BULK_DATA_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# User-Agent required by SEC
SEC_USER_AGENT = "Portin M&A Screener research@portin.local"

# Cache file path
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
SEC_CACHE_FILE = os.path.join(CACHE_DIR, "sec_companies.json")


class SECEdgarSearch:
    """
    Fast SEC EDGAR search using bulk data.
    No per-company API calls - filters locally.
    """
    
    def __init__(self, user_agent: str = SEC_USER_AGENT):
        self.user_agent = user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }
        self._companies = None  # Cached companies list
        self._sic_index = None  # SIC code -> companies index
        self._gemini = None
    
    def _get_gemini(self):
        """Lazy load Gemini model."""
        if self._gemini is None:
            try:
                import google.generativeai as genai
                from dotenv import load_dotenv
                load_dotenv()
                genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
                self._gemini = genai.GenerativeModel('gemini-2.5-flash')
            except Exception as e:
                logger.warning("Gemini not available for SEC filtering", error=str(e))
        return self._gemini
    
    def _load_bulk_data(self) -> List[Dict]:
        """
        Load SEC bulk company data (with SIC codes).
        Uses local cache for speed.
        """
        if self._companies is not None:
            return self._companies
        
        # Try cache first
        if os.path.exists(SEC_CACHE_FILE):
            try:
                with open(SEC_CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    # Check if cache is recent (less than 7 days old)
                    import time
                    if time.time() - cache.get('timestamp', 0) < 7 * 24 * 3600:
                        self._companies = cache.get('companies', [])
                        logger.info("Loaded SEC data from cache", count=len(self._companies))
                        return self._companies
            except Exception as e:
                logger.warning("Cache read failed", error=str(e))
        
        # Download fresh data
        logger.info("Downloading SEC bulk data...")
        
        try:
            response = requests.get(
                SEC_BULK_DATA_URL,
                headers=self.headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse the format: {"fields": [...], "data": [[...], ...]}
                fields = data.get('fields', [])
                rows = data.get('data', [])
                
                # Convert to list of dicts
                companies = []
                for row in rows:
                    company = dict(zip(fields, row))
                    companies.append({
                        "cik": str(company.get("cik", "")),
                        "name": company.get("name", ""),
                        "ticker": company.get("ticker", ""),
                        "exchange": company.get("exchange", ""),
                        "sic": str(company.get("sic", "")),
                    })
                
                self._companies = companies
                logger.info("Loaded SEC bulk data", count=len(companies))
                
                # Save to cache
                self._save_cache(companies)
                
                return companies
                
        except Exception as e:
            logger.error("Failed to load SEC bulk data", error=str(e))
        
        return []
    
    def _save_cache(self, companies: List[Dict]):
        """Save companies to local cache."""
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            import time
            with open(SEC_CACHE_FILE, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'companies': companies
                }, f)
            logger.info("Saved SEC cache", path=SEC_CACHE_FILE)
        except Exception as e:
            logger.warning("Failed to save cache", error=str(e))
    
    def _build_sic_index(self) -> Dict[str, List[Dict]]:
        """Build index of SIC code -> companies for fast lookup."""
        if self._sic_index is not None:
            return self._sic_index
        
        companies = self._load_bulk_data()
        self._sic_index = {}
        
        for company in companies:
            sic = company.get("sic", "")
            if sic:
                if sic not in self._sic_index:
                    self._sic_index[sic] = []
                self._sic_index[sic].append(company)
        
        logger.info("Built SIC index", unique_sics=len(self._sic_index))
        return self._sic_index
    
    def search_by_sic(self, sic_code: str, limit: int = 50) -> List[Dict]:
        """
        FAST search by SIC code using local index.
        No API calls - instant results.
        """
        logger.info("Searching SEC by SIC (fast)", sic=sic_code)
        
        sic_index = self._build_sic_index()
        companies = sic_index.get(str(sic_code), [])
        
        results = []
        for company in companies[:limit]:
            results.append({
                "name": company.get("name", ""),
                "ticker": company.get("ticker", ""),
                "cik": company.get("cik", ""),
                "sic": company.get("sic", ""),
                "exchange": company.get("exchange", ""),
                "source": "sec_edgar"
            })
        
        logger.info("SIC search complete", sic=sic_code, found=len(results))
        return results
    
    def search_by_name(self, query: str, limit: int = 20) -> List[Dict]:
        """
        FAST search by company name.
        Local filtering - no API calls.
        """
        logger.info("Searching SEC by name (fast)", query=query)
        
        companies = self._load_bulk_data()
        query_lower = query.lower()
        results = []
        
        for company in companies:
            name = company.get("name", "")
            if query_lower in name.lower():
                results.append({
                    "name": name,
                    "ticker": company.get("ticker", ""),
                    "cik": company.get("cik", ""),
                    "sic": company.get("sic", ""),
                    "exchange": company.get("exchange", ""),
                    "source": "sec_edgar"
                })
                if len(results) >= limit:
                    break
        
        logger.info("Name search complete", query=query, found=len(results))
        return results
    
    def search_by_keywords(self, keywords: List[str], limit: int = 30) -> List[Dict]:
        """
        Smart search using keywords + Gemini filtering.
        
        1. Find companies by SIC codes matching keywords
        2. Find companies by name matching keywords  
        3. Use Gemini to filter for relevance
        """
        logger.info("Searching SEC by keywords + Gemini", keywords=keywords)
        
        # Step 1: Get SIC codes for keywords
        sic_codes = get_sic_for_industry(keywords)
        
        # Step 2: Collect candidates from SIC matches
        candidates = []
        for sic in sic_codes[:5]:  # Limit SIC codes
            sic_results = self.search_by_sic(sic, limit=20)
            candidates.extend(sic_results)
        
        # Step 3: Add name matches
        for keyword in keywords[:3]:
            name_results = self.search_by_name(keyword, limit=10)
            candidates.extend(name_results)
        
        # Deduplicate by CIK
        seen_ciks = set()
        unique = []
        for c in candidates:
            cik = c.get("cik", "")
            if cik and cik not in seen_ciks:
                seen_ciks.add(cik)
                unique.append(c)
        
        logger.info("Found candidates", count=len(unique))
        
        # Step 4: Use Gemini to filter for relevance (if available)
        if len(unique) > limit:
            unique = self._filter_with_gemini(unique, keywords, limit)
        
        return unique[:limit]
    
    def _filter_with_gemini(self, companies: List[Dict], keywords: List[str], limit: int) -> List[Dict]:
        """Use Gemini to score and filter companies for relevance."""
        
        gemini = self._get_gemini()
        if not gemini:
            return companies[:limit]
        
        try:
            # Build company list for prompt
            company_list = "\n".join([
                f"{i+1}. {c['name']} (Ticker: {c.get('ticker', 'N/A')}, SIC: {c.get('sic', 'N/A')})"
                for i, c in enumerate(companies[:50])  # Limit to 50 for prompt
            ])
            
            prompt = f"""You are filtering SEC public companies for M&A research.

Target Industry Keywords: {', '.join(keywords)}

Companies to evaluate:
{company_list}

Return ONLY the numbers of companies that are MOST RELEVANT to the target industry.
Return as JSON array of numbers, e.g.: [1, 3, 7, 12, 15]

Focus on companies that:
- Match the industry keywords
- Are likely acquisition targets (not mega-corps like Apple/Microsoft)
- Have relevant business operations

JSON array only (no explanation):"""

            import time
            response = gemini.generate_content(prompt)
            time.sleep(2)  # Rate limit
            
            text = response.text.strip()
            if '```' in text:
                text = text.split('```')[1].replace('json', '').strip()
            
            indices = json.loads(text)
            
            # Filter companies by selected indices
            filtered = []
            for idx in indices:
                if 1 <= idx <= len(companies):
                    filtered.append(companies[idx - 1])
            
            logger.info("Gemini filtered companies", before=len(companies), after=len(filtered))
            return filtered[:limit]
            
        except Exception as e:
            logger.warning("Gemini filtering failed", error=str(e))
            return companies[:limit]
    
    @retry_api_call(max_attempts=3, min_wait=1, max_wait=10)
    def get_company_details(self, cik: str) -> Optional[Dict]:
        """
        Get detailed company info (for enrichment phase).
        Only call this for companies you actually want to enrich.
        """
        cik_padded = str(cik).zfill(10)
        url = SEC_SUBMISSIONS_URL.format(cik=cik_padded)
        
        logger.info("Fetching SEC company details", cik=cik)
        
        response = requests.get(url, headers=self.headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        
        return None


# ─────────────────────────────────────────────────────────────
# SIC CODE MAPPING
# ─────────────────────────────────────────────────────────────

# Common SIC codes for M&A research
SIC_CODES = {
    # Manufacturing
    "2631": "Paperboard Mills",
    "2650": "Paperboard Containers",
    "2670": "Converted Paper Products",
    "2750": "Commercial Printing",
    "2759": "Commercial Printing NEC",
    "3080": "Miscellaneous Plastics Products",
    "3089": "Plastics Products NEC",
    
    # Food
    "2000": "Food and Kindred Products",
    "2020": "Dairy Products",
    "2026": "Fluid Milk",
    "2030": "Canned & Preserved Fruits/Vegetables",
    "2050": "Bakery Products",
    "2080": "Beverages",
    
    # Packaging
    "2650": "Paperboard Containers & Boxes",
    "2670": "Converted Paper & Paperboard Products",
    "3085": "Plastics Bottles",
    "3086": "Plastics Foam Products",
    "3411": "Metal Cans",
    "3412": "Metal Shipping Containers",
    
    # Technology
    "7370": "Computer Programming Services",
    "7371": "Computer Programming Services",
    "7372": "Prepackaged Software",
    "7373": "Computer Integrated Systems Design",
    "7374": "Computer Processing & Data Prep",
}


def get_company_financials(company_name: str, cik: str = None) -> Dict:
    """
    Fetch verified financial data from SEC 10-K filings.
    
    Args:
        company_name: Company name to look up
        cik: Optional CIK number (faster if provided)
        
    Returns:
        Dict with revenue, fiscal_year, confidence level
    """
    sec = get_sec_search()
    
    # Find CIK if not provided
    if not cik:
        companies = sec._load_bulk_data()
        matches = [c for c in companies if company_name.lower() in c.get('name', '').lower()]
        if matches:
            cik = matches[0].get('cik')
    
    if not cik:
        return {"found": False, "reason": "Company not found in SEC database"}
    
    # Format CIK (pad with zeros to 10 digits)
    cik_padded = str(cik).zfill(10)
    
    try:
        # Fetch company submissions data
        url = SEC_SUBMISSIONS_URL.format(cik=cik_padded)
        response = requests.get(url, headers=sec.headers, timeout=30)
        
        if response.status_code != 200:
            return {"found": False, "reason": f"SEC API returned {response.status_code}"}
        
        data = response.json()
        
        # Get company info
        result = {
            "found": True,
            "name": data.get("name", ""),
            "cik": cik,
            "ticker": data.get("tickers", [""])[0] if data.get("tickers") else "",
            "sic": data.get("sic", ""),
            "sic_description": data.get("sicDescription", ""),
            "state": data.get("stateOfIncorporation", ""),
            "fiscal_year_end": data.get("fiscalYearEnd", ""),
            "confidence": "verified",
        }
        
        # Look for 10-K filings
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        
        # Find most recent 10-K
        for i, form in enumerate(forms):
            if form in ["10-K", "10-K/A"]:
                result["latest_10k_date"] = dates[i] if i < len(dates) else None
                break
        
        # Try to get revenue from XBRL data (company facts)
        try:
            facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
            facts_response = requests.get(facts_url, headers=sec.headers, timeout=30)
            
            if facts_response.status_code == 200:
                facts = facts_response.json()
                
                # Look for revenue in US-GAAP
                us_gaap = facts.get("facts", {}).get("us-gaap", {})
                
                # Try different revenue field names
                revenue_fields = [
                    "Revenues",
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "RevenueFromContractWithCustomerIncludingAssessedTax", 
                    "SalesRevenueNet",
                    "SalesRevenueGoodsNet",
                    "TotalRevenue",
                ]
                
                for field in revenue_fields:
                    if field in us_gaap:
                        units = us_gaap[field].get("units", {})
                        usd_values = units.get("USD", [])
                        
                        if usd_values:
                            # Get most recent annual value
                            annual_values = [
                                v for v in usd_values 
                                if v.get("form") in ["10-K"] and v.get("fp") == "FY"
                            ]
                            
                            if annual_values:
                                latest = sorted(annual_values, key=lambda x: x.get("end", ""), reverse=True)[0]
                                result["revenue_usd"] = latest.get("val")
                                result["revenue_year"] = latest.get("end", "")[:4]
                                result["revenue_field"] = field
                                break
                
        except Exception as e:
            logger.warning("XBRL revenue lookup failed", error=str(e))
        
        return result
        
    except Exception as e:
        logger.error("SEC financials lookup failed", error=str(e))
        return {"found": False, "reason": str(e)}


def get_sic_for_industry(industry_keywords: List[str]) -> List[str]:
    """
    Map industry keywords to SIC codes.
    
    Args:
        industry_keywords: List like ["packaging", "printing"]
        
    Returns:
        List of matching SIC codes
    """
    matches = []
    
    for keyword in industry_keywords:
        keyword_lower = keyword.lower()
        
        for sic, description in SIC_CODES.items():
            if keyword_lower in description.lower():
                matches.append(sic)
    
    return list(set(matches))


# Singleton instance
_sec_search = None

def get_sec_search() -> SECEdgarSearch:
    """Get singleton SEC search instance."""
    global _sec_search
    if _sec_search is None:
        _sec_search = SECEdgarSearch()
    return _sec_search

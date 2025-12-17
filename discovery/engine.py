#!/usr/bin/env python3
"""
AGGRESSIVE MULTI-SOURCE DISCOVERY ENGINE
Finds companies across multiple sources based on search criteria

Sources:
1. Google Search (via Serper) - finds directories and lists
2. Web scraping (Firecrawl + HTTP) - extracts from directories
3. Gemini extraction - pulls company names from text
4. Apollo.io (API) - if configured
5. Framework for LinkedIn/ZoomInfo - ready to implement
"""

import os
import json
import time
import re
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class AggressiveDiscoveryEngine:
    """
    Multi-source company discovery
    No holds barred approach
    """
    
    def __init__(self, criteria: Dict):
        self.criteria = criteria
        self.gemini = genai.GenerativeModel('gemini-2.5-flash')
        
        # API keys
        self.serper_key = os.getenv('SERPER_KEY')
        self.firecrawl_key = os.getenv('FIRECRAWL_KEY')
        self.apollo_key = os.getenv('APOLLO_KEY')
        self.companies_house_key = os.getenv('COMPANIES_HOUSE_API_KEY')
        
        # Results storage
        self.all_companies = []
        self.sources_used = []
        
        # Stats
        self.stats = {
            'google_searches': 0,
            'pages_scraped': 0,
            'gemini_extractions': 0,
            'apollo_calls': 0,
            'total_found': 0
        }
        
        # Search engine preference (default: let user choose)
        self.search_engine = None  # 'google' or 'duckduckgo'
        
        # Database session (for persistence)
        self.session_id = None
        
        # Scraped URLs cache (to avoid re-scraping)
        self._scraped_urls = set()
    
    def ask_search_preference(self):
        """Ask user which search engine to use."""
        print("\n" + "─"*50)
        print("SEARCH ENGINE SELECTION")
        print("─"*50)
        print("\n[1] Google (via Serper API) - Better results, uses API quota")
        print("[2] DuckDuckGo - Free, no API key needed, slightly less results")
        print("[3] Both - Try Google first, fallback to DDG if quota exceeded\n")
        
        while True:
            choice = input("Select search engine [1/2/3]: ").strip()
            
            if choice == "1":
                self.search_engine = "google"
                print("\n[INFO] Using Google (Serper API)\n")
                return
            elif choice == "2":
                self.search_engine = "duckduckgo"
                print("\n[INFO] Using DuckDuckGo (Free)\n")
                return
            elif choice == "3":
                self.search_engine = "both"
                print("\n[INFO] Using Google with DuckDuckGo fallback\n")
                return
            else:
                print("[ERROR] Please enter 1, 2, or 3")
    
    def discover_all_sources(self) -> List[Dict]:
        """
        Run discovery across all available sources
        """
        
        # Ask user for search engine preference
        if self.search_engine is None:
            self.ask_search_preference()
        
        print("[INFO] Starting multi-source discovery...\n")
        
        # Initialize database session
        self._init_database_session()
        
        # Show database stats
        self._show_database_stats()
        
        results = {}
        
        # Determine which sources we can use
        available_sources = self.check_available_sources()
        
        # Override based on user preference
        if self.search_engine == "duckduckgo":
            available_sources = [s for s in available_sources if s != 'google_directories']
            available_sources.append('duckduckgo')
        elif self.search_engine == "both":
            if 'google_directories' in available_sources:
                available_sources.append('duckduckgo')  # As fallback
        
        print(f"Available sources: {', '.join(available_sources)}\n")
        
        # Run sources in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            
            if 'google_directories' in available_sources and self.search_engine != "duckduckgo":
                futures[executor.submit(self.discover_via_google)] = 'Google Directories'
            
            if 'duckduckgo' in available_sources or self.search_engine == "duckduckgo":
                futures[executor.submit(self.discover_via_duckduckgo)] = 'DuckDuckGo'
            
            if 'sec_edgar' in available_sources:
                futures[executor.submit(self.discover_via_sec_edgar)] = 'SEC EDGAR'
            
            if 'opencorporates' in available_sources:
                futures[executor.submit(self.discover_via_opencorporates)] = 'OpenCorporates'
            
            if 'apollo' in available_sources:
                futures[executor.submit(self.discover_via_apollo)] = 'Apollo.io'
            
            # Process results as they complete
            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    companies = future.result()
                    results[source_name] = companies
                    print(f"[SUCCESS] {source_name}: Found {len(companies)} companies")
                except Exception as e:
                    print(f"[ERROR] {source_name}: Error - {e}")
        
        # Merge and deduplicate
        print("\n[INFO] Merging results...")
        all_companies = self.merge_and_deduplicate(results)
        
        # Filter out already-known companies from database
        new_companies = self._filter_known_companies(all_companies)
        
        # Score companies
        print("[INFO] Scoring companies by fit...")
        scored_companies = self.score_companies(new_companies)
        
        # Save results (both JSON and database)
        self.save_results(scored_companies)
        
        return scored_companies
    
    def check_available_sources(self) -> List[str]:
        """
        Check which sources are configured and available
        """
        
        available = []
        
        if self.serper_key:
            available.append('google_directories')
        else:
            print("[INFO] No SERPER_KEY - Google search disabled")
        
        if self.apollo_key:
            available.append('apollo')
        else:
            print("[INFO] No APOLLO_KEY - Apollo.io disabled")
        
        if self.companies_house_key:
            available.append('companies_house')
        else:
            print("[INFO] No COMPANIES_HOUSE_API_KEY - UK Companies House disabled")
        
        # These are always available (free, no key)
        available.append('sec_edgar')
        available.append('opencorporates')
        available.append('http_scraping')
        
        return available
    
    def discover_via_google(self) -> List[Dict]:
        """
        Discover companies via Google Search + scraping
        """
        
        print("\n[INFO] Searching Google for companies (7-phase comprehensive strategy)...\n")
        
        # Step 1: Generate comprehensive search queries
        search_queries = self.generate_search_queries()
        
        # Step 2: Search with Serper - use MORE queries for better coverage
        directory_urls = []
        for query in search_queries[:20]:  # Increased from 10 to 20
            print(f"   Searching: {query}")
            urls = self.search_google(query)
            directory_urls.extend(urls)
            time.sleep(0.5)  # Faster rate limiting
        
        # Deduplicate URLs
        directory_urls = list(set(directory_urls))
        print(f"\n   Found {len(directory_urls)} unique pages to analyze")
        
        # Filter out already-scraped URLs
        directory_urls = self._filter_scraped_urls(directory_urls)
        print(f"   New pages to scrape: {len(directory_urls)}")
        
        # Step 3: Scrape and extract companies
        print("\n[INFO] Scraping pages for company names...\n")
        
        companies = []
        for url in directory_urls[:30]:  # Increased from 20 to 30
            print(f"   Scraping: {url[:60]}...")
            
            try:
                page_content = self.scrape_page(url)
                
                if page_content:
                    # Extract companies with Gemini
                    extracted = self.extract_companies_from_text(page_content, url)
                    companies.extend(extracted)
                    print(f"      -> Found {len(extracted)} companies")
                    
                    # Mark URL as scraped with count
                    self._mark_url_scraped(url, len(extracted))
                    
            except Exception as e:
                print(f"      → Error: {e}")
                self._mark_url_scraped(url, 0)  # Still mark as scraped to avoid retry
            
            time.sleep(2)  # Be nice
        
        return companies
    
    def discover_via_duckduckgo(self) -> List[Dict]:
        """
        Discover companies via DuckDuckGo Search + scraping (FREE)
        """
        
        print("\n[INFO] Searching DuckDuckGo for company directories...\n")
        
        # Import DDG search
        try:
            from sources.ddg_search import DuckDuckGoSearch
            ddg = DuckDuckGoSearch(rate_limit_delay=2.0)
        except ImportError:
            print("[ERROR] ddg_search module not found. Run: pip install duckduckgo-search")
            return []
        
        # Step 1: Generate search queries using Gemini
        search_queries = self.generate_search_queries()
        
        # Step 2: Search with DuckDuckGo
        directory_urls = []
        for query in search_queries[:5]:
            print(f"   Searching DDG: {query}")
            try:
                results = ddg.search(query, max_results=10)
                for r in results:
                    url = r.get("href", "")
                    if url and self._is_valid_directory_url(url):
                        directory_urls.append(url)
            except Exception as e:
                print(f"      DDG error: {e}")
            time.sleep(2)
        
        # Deduplicate
        directory_urls = list(set(directory_urls))
        print(f"\n   Found {len(directory_urls)} potential directory pages")
        
        # Step 3: Scrape directory pages
        print("\n[INFO] Scraping directory pages...\n")
        
        companies = []
        for url in directory_urls[:10]:
            print(f"   Scraping: {url[:60]}...")
            
            try:
                page_content = self.scrape_page(url)
                
                if page_content:
                    extracted = self.extract_companies_from_text(page_content, url)
                    companies.extend(extracted)
                    print(f"      -> Found {len(extracted)} companies")
                    
            except Exception as e:
                print(f"      → Error: {e}")
            
            time.sleep(2)
        
        return companies
    
    def _is_valid_directory_url(self, url: str) -> bool:
        """Check if URL is likely a directory page (not social media etc)."""
        url_lower = url.lower()
        
        skip_domains = [
            "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
            "youtube.com", "instagram.com", "reddit.com", "quora.com",
            "amazon.com", "ebay.com", "yelp.com", "glassdoor.com",
            "bloomberg.com", "reuters.com", "forbes.com", "medium.com"
        ]
        
        for domain in skip_domains:
            if domain in url_lower:
                return False
        
        return True
    
    def discover_via_sec_edgar(self) -> List[Dict]:
        """
        Discover US public companies via SEC EDGAR (FREE).
        Uses bulk data + Gemini filtering for fast, smart results.
        """
        
        print("\n[INFO] Searching SEC EDGAR for US public companies...\n")
        
        try:
            from sources.sec_edgar import SECEdgarSearch
        except ImportError:
            print("[ERROR] sec_edgar module not found")
            return []
        
        sec = SECEdgarSearch()
        companies = []
        
        # Get industry keywords from criteria
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        
        # Combine keywords for smart search
        all_keywords = industries + keywords
        
        if all_keywords:
            print(f"   Searching with keywords: {all_keywords[:5]}...")
            
            try:
                # Use the new optimized search with Gemini filtering
                results = sec.search_by_keywords(all_keywords, limit=30)
                
                for r in results:
                    companies.append({
                        "name": r.get("name", ""),
                        "ticker": r.get("ticker", ""),
                        "cik": r.get("cik", ""),
                        "sic": r.get("sic", ""),
                        "exchange": r.get("exchange", ""),
                        "location": "USA",
                        "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={r.get('cik')}",
                        "info": f"Public company. Ticker: {r.get('ticker', 'N/A')}. Exchange: {r.get('exchange', 'N/A')}",
                    })
                    print(f"      Found: {r.get('name', 'Unknown')[:50]}")
                    
            except Exception as e:
                print(f"      SEC search error: {e}")
        
        print(f"\n   SEC EDGAR found {len(companies)} public companies")
        return companies
    
    def discover_via_opencorporates(self) -> List[Dict]:
        """
        Discover companies globally via OpenCorporates (FREE).
        Searches by industry keywords in US and UK jurisdictions.
        """
        
        print("\n[INFO] Searching OpenCorporates for company registry data...\n")
        
        try:
            from sources.opencorporates import OpenCorporatesSearch
        except ImportError:
            print("[ERROR] opencorporates module not found")
            return []
        
        oc = OpenCorporatesSearch()
        companies = []
        
        # Get industry keywords from criteria
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        
        # Determine geography
        geography = self.criteria.get('geography', {})
        regions = geography.get('regions', ['USA'])
        
        # Build search keywords
        search_terms = (industries + keywords)[:3]  # Limit to 3
        
        for term in search_terms:
            print(f"   Searching OpenCorporates for '{term}'...")
            try:
                # Search all (will include US, UK, etc.)
                results = oc.search(term, limit=15)
                
                for r in results:
                    companies.append({
                        "name": r.get("name", ""),
                        "company_number": r.get("company_number", ""),
                        "jurisdiction": r.get("jurisdiction", ""),
                        "status": r.get("status", ""),
                        "location": r.get("address", "") or r.get("jurisdiction", "").upper(),
                        "source_url": r.get("opencorporates_url", ""),
                        "info": f"Registry: {r.get('jurisdiction', '').upper()}. Status: {r.get('status', 'unknown')}",
                    })
                    
            except Exception as e:
                print(f"      OpenCorporates error: {e}")
        
        # Deduplicate by name
        seen_names = set()
        unique_companies = []
        for c in companies:
            name_lower = c.get("name", "").lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                unique_companies.append(c)
        
        print(f"\n   OpenCorporates found {len(unique_companies)} companies")
        return unique_companies
    
    def generate_search_queries(self) -> List[str]:
        """
        Generate COMPREHENSIVE search queries for maximum discovery.
        Uses 6-phase strategy with Gemini-assisted expansion.
        Goal: Find as many relevant companies as possible.
        """
        
        # Extract key info from criteria
        reference_companies = self.criteria.get('reference_companies', [])
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        geography = self.criteria.get('geography', {})
        regions = geography.get('regions', ['USA', 'United States'])
        countries = geography.get('countries', ['US'])
        
        ref_company = reference_companies[0] if reference_companies else ""
        main_industry = industries[0] if industries else "company"
        
        queries = []
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 1: Reference Company Competitors (HIGH VALUE)
        # ─────────────────────────────────────────────────────────────
        if ref_company:
            # Direct competitor queries
            queries.extend([
                f'"{ref_company}" competitors',
                f'"{ref_company}" top competitors',
                f'"{ref_company}" main competitors',
                f'"{ref_company}" biggest competitors',
                f'top 10 {ref_company} competitors',
                f'who competes with {ref_company}',
                f'{ref_company} competitor analysis',
                f'{ref_company} competitive landscape',
            ])
            
            # Alternative/similar queries
            queries.extend([
                f'companies like "{ref_company}"',
                f'companies similar to {ref_company}',
                f'"{ref_company}" alternatives',
                f'best alternatives to {ref_company}',
                f'{ref_company} vs',
                f'{ref_company} vs competitors',
            ])
            
            # Industry-specific competitor queries
            for region in regions[:2]:
                queries.extend([
                    f'best {main_industry} companies similar to {ref_company}',
                    f'competitors of {ref_company} {region}',
                    f'top {ref_company} alternatives {region}',
                    f'{ref_company} competitors {region}',
                    f'{main_industry} competitors to {ref_company}',
                ])
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 2: Industry + Region Combinations (COMPREHENSIVE)
        # ─────────────────────────────────────────────────────────────
        for ind in industries[:3]:
            for region in regions[:3]:
                queries.extend([
                    f'{ind} companies {region}',
                    f'{ind} manufacturers {region}',
                    f'{ind} suppliers {region}',
                    f'top {ind} companies {region}',
                    f'best {ind} companies {region}',
                    f'leading {ind} manufacturers {region}',
                    f'{ind} companies list {region}',
                    f'{ind} industry {region}',
                ])
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 3: Keyword + Modifier Combinations
        # ─────────────────────────────────────────────────────────────
        modifiers = ['companies', 'manufacturers', 'suppliers', 'brands', 'producers', 'vendors']
        for keyword in keywords[:4]:
            for modifier in modifiers[:3]:
                for region in regions[:2]:
                    queries.append(f'{keyword} {modifier} {region}')
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 4: "Top/Best/List" Queries (HIGH HIT RATE)
        # ─────────────────────────────────────────────────────────────
        list_prefixes = ['top 10', 'top 20', 'top 50', 'best', 'leading', 'biggest', 'largest', 'top']
        for prefix in list_prefixes:
            for region in regions[:2]:
                queries.extend([
                    f'{prefix} {main_industry} companies {region}',
                    f'{prefix} {main_industry} manufacturers {region}',
                ])
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 5: Niche / Specialty / Size-Based
        # ─────────────────────────────────────────────────────────────
        niche_terms = ['small', 'mid-size', 'startup', 'private', 'family-owned', 'boutique', 'custom', 'specialty']
        for term in niche_terms[:5]:
            for region in regions[:2]:
                queries.append(f'{term} {main_industry} companies {region}')
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 6: Association / Directory / Trade
        # ─────────────────────────────────────────────────────────────
        for region in regions[:2]:
            queries.extend([
                f'{main_industry} association members {region}',
                f'{main_industry} trade association {region}',
                f'{main_industry} industry directory {region}',
                f'{main_industry} company directory {region}',
                f'{main_industry} business directory {region}',
                f'{main_industry} expo exhibitors {region}',
                f'{main_industry} conference exhibitors {region}',
            ])
        
        # ─────────────────────────────────────────────────────────────
        for keyword in keywords[:3]:
            for region in regions[:2]:
                queries.extend([
                    f'{keyword} {region}',
                    f'buy {keyword} {region}',
                    f'{keyword} wholesale {region}',
                    f'{keyword} distributors {region}',
                ])
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 8: Competitor-Focused Queries (DEDICATED)
        # ─────────────────────────────────────────────────────────────
        if ref_company:
            # Top competitors queries
            queries.extend([
                f'top {ref_company} competitors',
                f'{ref_company} biggest competitors',
                f'{ref_company} main competitors',
                f'top 5 {ref_company} competitors',
                f'top 10 {ref_company} competitors',
                f'{ref_company} competitor list',
                f'{ref_company} competitor companies',
            ])
            
            # Analysis/comparison queries
            queries.extend([
                f'{ref_company} competitor analysis',
                f'{ref_company} competitive analysis',
                f'{ref_company} market competitors',
                f'{ref_company} industry competitors',
                f'who competes with {ref_company}',
                f'{ref_company} competition',
            ])
            
            # Vs queries (often yield competitor lists)
            queries.extend([
                f'{ref_company} vs',
                f'{ref_company} versus',
                f'{ref_company} compared to',
                f'alternatives to {ref_company}',
                f'{ref_company} or similar',
            ])
        
        # Deduplicate and shuffle for variety
        seen = set()
        unique_queries = []
        for q in queries:
            q_lower = q.lower().strip()
            if q_lower not in seen and len(q_lower) > 5:
                seen.add(q_lower)
                unique_queries.append(q)
        
        # Optionally expand with Gemini for even more ideas
        if len(unique_queries) < 30:
            extra_queries = self._expand_queries_with_gemini(ref_company, main_industry, keywords, regions)
            for q in extra_queries:
                if q.lower() not in seen:
                    unique_queries.append(q)
                    seen.add(q.lower())
        
        print(f"\n   Generated {len(unique_queries)} search queries:")
        for i, q in enumerate(unique_queries[:5], 1):
            print(f"      {i}. {q}")
        if len(unique_queries) > 5:
            print(f"      ... and {len(unique_queries) - 5} more")
        
        return unique_queries[:40]  # Return up to 40 queries for comprehensive coverage
    
    def _expand_queries_with_gemini(self, ref_company: str, industry: str, keywords: list, regions: list) -> List[str]:
        """Use Gemini to generate additional creative search queries."""
        try:
            prompt = f"""Generate 15 unique Google search queries to find companies in this industry:

Industry: {industry}
Keywords: {', '.join(keywords[:5])}
Reference company (find similar): {ref_company or 'N/A'}
Target regions: {', '.join(regions[:3])}

Generate VARIED queries that would help find:
- Competitors of the reference company
- Companies in the same industry
- Different angles (suppliers, manufacturers, brands, wholesalers)
- Trade associations and directories
- Award winners and industry leaders

Return ONLY a JSON array of query strings, no explanation:
["query 1", "query 2", ...]"""

            response = self.gemini.generate_content(prompt)
            text = response.text.strip()
            
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            queries = json.loads(text)
            print(f"   [Gemini] Added {len(queries)} AI-generated queries")
            return queries[:15]
            
        except Exception as e:
            print(f"   [Gemini] Query expansion failed: {e}")
            return []
    
    def search_google(self, query: str) -> List[str]:
        """
        Search Google via Serper API
        """
        
        if not self.serper_key:
            return []
        
        try:
            url = "https://google.serper.dev/search"
            headers = {
                'X-API-KEY': self.serper_key,
                'Content-Type': 'application/json'
            }
            payload = {
                "q": query,
                "num": 10
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            self.stats['google_searches'] += 1
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('organic', [])
                
                # Filter for directory-like URLs
                urls = []
                for result in results:
                    url = result.get('link', '')
                    
                    # Prioritize directory-like URLs
                    if any(keyword in url.lower() for keyword in [
                        'directory', 'list', 'members', 'companies', 
                        'database', 'association', 'chamber'
                    ]):
                        urls.append(url)
                    else:
                        urls.append(url)
                
                return urls[:5]  # Top 5 URLs per query
                
        except Exception as e:
            print(f"   Serper error: {e}")
        
        return []
    
    def scrape_page(self, url: str) -> str:
        """
        Scrape a web page using priority:
        1. Crawl4AI (handles JS, returns Markdown)
        2. Firecrawl API (backup)
        3. Basic HTTP (fallback)
        """
        
        # Try Crawl4AI first (best for JS-heavy sites)
        try:
            from sources.crawl4ai_scraper import scrape_url, check_crawl4ai_available
            
            if check_crawl4ai_available():
                content = scrape_url(url, timeout=20)
                if content and len(content) > 200:
                    self.stats['pages_scraped'] += 1
                    return content
        except ImportError:
            pass  # Crawl4AI not installed
        except Exception as e:
            print(f"      Crawl4AI error: {e}")
        
        # Try Firecrawl second (API-based)
        if self.firecrawl_key and self.stats['pages_scraped'] < 20:
            content = self.scrape_with_firecrawl(url)
            if content:
                self.stats['pages_scraped'] += 1
                return content
        
        # Fallback to basic HTTP
        content = self.scrape_with_http(url)
        if content:
            self.stats['pages_scraped'] += 1
        
        return content
    
    def scrape_with_firecrawl(self, url: str) -> str:
        """
        Scrape with Firecrawl API
        """
        
        try:
            api_url = "https://api.firecrawl.dev/v1/scrape"
            headers = {
                'Authorization': f'Bearer {self.firecrawl_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'url': url,
                'formats': ['markdown'],
                'onlyMainContent': True
            }
            
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('markdown', '')[:10000]
                
        except Exception as e:
            pass
        
        return ""
    
    def scrape_with_http(self, url: str) -> str:
        """
        Simple HTTP scraping fallback
        """
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Simple text extraction
                text = response.text
                
                # Remove scripts and styles
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                
                # Clean whitespace
                text = ' '.join(text.split())
                
                return text[:10000]
                
        except Exception as e:
            pass
        
        return ""
    
    def extract_companies_from_text(self, text: str, source_url: str) -> List[Dict]:
        """
        Use Gemini to extract company names from scraped text
        """
        
        prompt = f"""Extract company names from this directory/list.

Search criteria (only include companies matching this):
Industry: {self.criteria.get('industry', {}).get('industry', [])}
Location: {self.criteria.get('geography', {}).get('regions', [])}

Extract company information and return as JSON array:
[
  {{
    "name": "Company Name",
    "location": "City, State/Country (if mentioned)",
    "info": "brief description (if available)",
    "source_url": "{source_url}"
  }}
]

Only include companies that match the industry criteria.
Skip individual people, generic terms, or non-company entries.
Return empty array if no companies found.

Text to analyze:
{text[:8000]}

JSON only:"""
        
        try:
            response = self.gemini.generate_content(prompt)
            text = response.text.strip()
            
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            companies = json.loads(text)
            self.stats['gemini_extractions'] += 1
            
            # Wait for rate limit
            time.sleep(6)
            
            return companies if isinstance(companies, list) else []
            
        except Exception as e:
            print(f"      Gemini extraction error: {e}")
            return []
    
    def discover_via_apollo(self) -> List[Dict]:
        """
        Discover companies via Apollo.io API
        """
        
        print("\n[INFO] Searching Apollo.io...\n")
        
        if not self.apollo_key:
            print("   [WARNING] Apollo API key not configured")
            print("   Sign up at https://www.apollo.io/")
            return []
        
        # Note: This is a template - Apollo API structure may vary
        # User needs to implement based on their Apollo plan
        
        print("   [INFO] Apollo integration ready")
        print("   [TODO] Implement Apollo.io API calls")
        print("   Docs: https://apolloio.github.io/apollo-api-docs/\n")
        
        return []
    
    def merge_and_deduplicate(self, results: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Merge results from multiple sources and remove duplicates
        """
        
        all_companies = []
        
        for source, companies in results.items():
            for company in companies:
                company['discovery_source'] = source
                all_companies.append(company)
        
        # Deduplicate by company name (case-insensitive)
        seen = set()
        unique_companies = []
        
        for company in all_companies:
            name = company.get('name', '').lower().strip()
            
            if name and name not in seen:
                seen.add(name)
                unique_companies.append(company)
        
        self.stats['total_found'] = len(unique_companies)
        
        return unique_companies
    
    def score_companies(self, companies: List[Dict]) -> List[Dict]:
        """
        Score companies by similarity to reference company using Gemini.
        Compares each company against the reference to find best M&A targets.
        """
        
        if not companies:
            return []
        
        # Get reference company info
        reference_companies = self.criteria.get('reference_companies', [])
        ref_company = reference_companies[0] if reference_companies else None
        
        # Get criteria details
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        geography = self.criteria.get('geography', {})
        regions = geography.get('regions', ['USA'])
        revenue_criteria = self.criteria.get('revenue', {})
        
        print(f"\n[INFO] Scoring {len(companies)} companies with Gemini...")
        
        if ref_company:
            print(f"   Reference: {ref_company}")
        
        # Score in batches to avoid rate limits
        batch_size = 10
        scored = []
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            print(f"   Scoring batch {i//batch_size + 1}/{(len(companies) + batch_size - 1)//batch_size}...")
            
            try:
                batch_scored = self._score_batch_with_gemini(
                    batch, 
                    ref_company, 
                    industries + keywords,
                    regions,
                    revenue_criteria
                )
                scored.extend(batch_scored)
                
                # Rate limit
                time.sleep(3)
                
            except Exception as e:
                print(f"      Gemini scoring failed: {e}")
                # Fallback to simple scoring for this batch
                for company in batch:
                    company['fit_score'] = self._simple_score(company, keywords, regions)
                    company['score_reason'] = "Simple keyword match (Gemini unavailable)"
                    scored.append(company)
        
        # Sort by score
        scored.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
        
        print(f"   Scoring complete. Top score: {scored[0].get('fit_score', 0) if scored else 0}")
        
        return scored
    
    def _score_batch_with_gemini(
        self, 
        companies: List[Dict], 
        ref_company: str,
        industry_keywords: List[str],
        regions: List[str],
        revenue_criteria: Dict
    ) -> List[Dict]:
        """
        Use Gemini to score a batch of companies.
        """
        
        # Build company list for prompt
        company_summaries = []
        for i, c in enumerate(companies):
            summary = f"{i+1}. {c.get('name', 'Unknown')}"
            if c.get('location'):
                summary += f" | Location: {c.get('location')}"
            if c.get('info'):
                summary += f" | Info: {c.get('info', '')[:150]}"
            if c.get('ticker'):
                summary += f" | Ticker: {c.get('ticker')}"
            company_summaries.append(summary)
        
        company_list = "\n".join(company_summaries)
        
        # Build reference context
        ref_context = ""
        if ref_company:
            ref_context = f"""
REFERENCE COMPANY (find similar companies to this):
- Name: {ref_company}
- We are looking for companies similar to {ref_company} for potential M&A

"""
        
        prompt = f"""You are an M&A analyst scoring potential acquisition targets.

{ref_context}TARGET CRITERIA:
- Industry: {', '.join(industry_keywords[:5])}
- Geography: {', '.join(regions)}
- Revenue Range: {revenue_criteria.get('revenue_min_millions', 'N/A')}M - {revenue_criteria.get('revenue_max_millions', 'N/A')}M USD

COMPANIES TO SCORE:
{company_list}

For each company, provide:
1. A fit score from 0-100 (how well it matches criteria/reference)
2. A brief reason (1 sentence)

Score higher (70-100) if:
- Similar industry to reference company
- Matches geographic criteria
- Likely in target revenue range
- Good strategic fit for M&A

Score lower (0-40) if:
- Wrong industry
- Wrong geography  
- Too large (Fortune 500) or too small
- Not a real company match

Return as JSON array:
[
  {{"company_number": 1, "score": 75, "reason": "Same industry as reference, US-based"}},
  {{"company_number": 2, "score": 45, "reason": "Related industry but wrong geography"}}
]

JSON only:"""

        response = self.gemini.generate_content(prompt)
        text = response.text.strip()
        
        # Parse JSON
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        
        scores = json.loads(text)
        
        # Apply scores to companies
        score_map = {s['company_number']: s for s in scores}
        
        for i, company in enumerate(companies):
            score_data = score_map.get(i + 1, {})
            company['fit_score'] = score_data.get('score', 50)
            company['score_reason'] = score_data.get('reason', 'No reason provided')
        
        return companies
    
    def _simple_score(self, company: Dict, keywords: List[str], regions: List[str]) -> int:
        """Fallback simple scoring when Gemini unavailable."""
        score = 50
        
        # Location match
        if company.get('location'):
            for region in regions:
                if region.lower() in company['location'].lower():
                    score += 20
                    break
        
        # Keyword match
        if company.get('info'):
            for term in keywords:
                if term.lower() in company['info'].lower():
                    score += 10
                    break
        
        return min(score, 100)
    
    def save_results(self, companies: List[Dict]):
        """
        Save discovery results to both JSON and database.
        JSON for quick viewing, database for persistence.
        """
        
        output = {
            'criteria': self.criteria,
            'stats': self.stats,
            'companies': companies,
            'timestamp': time.time(),
            'session_id': self.session_id
        }
        
        # Get the project root directory (parent of discovery/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, 'output')
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, 'discovered_companies.json')
        
        # Save to JSON (for quick viewing)
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n[SUCCESS] Results saved to output/discovered_companies.json")
        
        # Save to database (for persistence)
        self._save_to_database(companies)
    
    def _init_database_session(self):
        """Initialize database and create session."""
        try:
            from data.db import init_database, create_session, DB_PATH
            import os
            
            # Ensure database exists
            if not os.path.exists(DB_PATH):
                init_database()
            
            # Create new session
            self.session_id = create_session(self.criteria)
            print(f"[DB] Created session #{self.session_id}")
            
        except Exception as e:
            print(f"[WARNING] Database init failed: {e}")
            self.session_id = None
    
    def _show_database_stats(self):
        """Show stats about existing companies in database."""
        try:
            from data.db import get_database_stats
            
            stats = get_database_stats()
            
            if stats['total_companies'] > 0:
                print(f"[DB] Database: {stats['unique_companies']} unique companies from {stats['total_sessions']} sessions")
                print(f"     ({stats['discovered']} discovered, {stats['enriched']} enriched)\n")
            else:
                print(f"[DB] Database: Empty (first run)\n")
                
        except Exception as e:
            print(f"[WARNING] Could not get database stats: {e}")
    
    def _filter_known_companies(self, companies: List[Dict]) -> List[Dict]:
        """Filter out companies already in the database."""
        try:
            from data.db import filter_new_companies
            
            before_count = len(companies)
            new_companies = filter_new_companies(companies)
            after_count = len(new_companies)
            
            if before_count > after_count:
                print(f"[DB] Filtered: {before_count - after_count} already-known companies")
                print(f"[DB] New companies: {after_count}")
            
            return new_companies
            
        except Exception as e:
            print(f"[WARNING] Deduplication failed: {e}")
            return companies
    
    def _save_to_database(self, companies: List[Dict]):
        """Save discovered companies to database."""
        if not self.session_id:
            return
        
        try:
            from data.db import add_companies_batch, update_session_status
            
            # Convert companies to DB format
            db_companies = []
            for c in companies:
                db_companies.append({
                    "name": c.get("name", ""),
                    "domain": c.get("domain", ""),
                    "website": c.get("source_url", "") or c.get("website", ""),
                    "source": c.get("source", "discovery"),
                    "score": c.get("fit_score", 50),
                })
            
            # Add to database
            added = add_companies_batch(
                session_id=self.session_id,
                companies=db_companies,
                source="discovery"
            )
            
            # Update session status
            update_session_status(self.session_id, "completed")
            
            print(f"[DB] Saved {added} companies to database (session #{self.session_id})")
            
        except Exception as e:
            print(f"[WARNING] Database save failed: {e}")
    
    def _filter_scraped_urls(self, urls: List[str]) -> List[str]:
        """Filter out URLs that have already been scraped."""
        try:
            from data.db import filter_new_urls
            
            return filter_new_urls(urls)
            
        except Exception as e:
            print(f"[WARNING] URL filtering failed: {e}")
            return urls
    
    def _mark_url_scraped(self, url: str, companies_found: int = 0):
        """Mark a URL as scraped in the database."""
        try:
            from data.db import mark_url_scraped
            
            mark_url_scraped(url, companies_found)
            
        except Exception as e:
            pass  # Silently ignore - not critical
    
    def _load_scraped_urls(self):
        """Load already-scraped URLs into local cache."""
        try:
            from data.db import get_scraped_urls
            
            self._scraped_urls = get_scraped_urls()
            if self._scraped_urls:
                print(f"[DB] Loaded {len(self._scraped_urls)} cached URLs")
                
        except Exception as e:
            self._scraped_urls = set()


def main():
    """
    Run discovery engine
    """
    
    # Get the project root directory (parent of discovery/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    criteria_file = os.path.join(project_root, 'output', 'search_criteria.json')
    
    # Check for criteria file
    if os.path.exists(criteria_file):
        print("[INFO] Loading search criteria...\n")
        
        with open(criteria_file, 'r') as f:
            data = json.load(f)
            criteria = data.get('criteria', {})
    else:
        print("[ERROR] No search criteria found!")
        print("Run: python lead_researcher.py first\n")
        return
    
    # Initialize engine
    engine = AggressiveDiscoveryEngine(criteria)
    
    # Discover
    companies = engine.discover_all_sources()
    
    # Summary
    print("\n" + "="*70)
    print(" DISCOVERY COMPLETE")
    print("="*70)
    print(f"\nTotal companies found: {len(companies)}")
    print(f"Google searches: {engine.stats['google_searches']}")
    print(f"Pages scraped: {engine.stats['pages_scraped']}")
    print(f"Gemini extractions: {engine.stats['gemini_extractions']}")
    
    if companies:
        print(f"\nTop 10 companies by fit score:")
        for i, company in enumerate(companies[:10], 1):
            print(f"\n{i}. {company['name']} (Score: {company['fit_score']}/100)")
            if company.get('location'):
                print(f"   Location: {company['location']}")
            if company.get('info'):
                print(f"   Info: {company['info'][:100]}...")
    
    print("\n" + "="*70)
    print("\nNext steps:")
    print("1. Review discovered_companies.json")
    print("2. Run enrichment: python ultra_demo_screener.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

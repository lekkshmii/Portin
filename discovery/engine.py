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
from config.model_config import get_current_model

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class AggressiveDiscoveryEngine:
    """
    Multi-source company discovery
    No holds barred approach
    """
    
    def __init__(self, criteria: Dict):
        self.criteria = criteria
        self.gemini = genai.GenerativeModel(get_current_model())
        
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
        
        # Reference company profiles (populated by profiling step)
        self.reference_profiles = []
        self.enhanced_keywords = []
    
    def ask_search_preference(self):
        """Ask user which search engine to use."""
        # Non-blocking check for dashboard/CLI pre-config
        if self.search_engine:
            print(f"[INFO] Using pre-configured search engine: {self.search_engine}")
            return

        print("\n" + "─"*50)
        print("SEARCH ENGINE SELECTION")
        print("─"*50)
        print("\n[1] Google (via Serper API) - Better results, uses API quota")
        print("[2] DuckDuckGo - Free, no API key needed, slightly less results")
        print("[3] Both - Try Google first, fallback to DDG if quota exceeded")
        print("[4] Google Grounding - Uses Gemini's real-time web search (FREE until Jan 2026)\n")

        while True:
            choice = input("Select search engine [1/2/3/4]: ").strip()

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
            elif choice == "4":
                self.search_engine = "grounding"
                print("\n[INFO] Using Google Grounding (Gemini real-time search)\n")
                return
            else:
                print("[ERROR] Please enter 1, 2, 3, or 4")
    
    def discover_all_sources(self) -> List[Dict]:
        """
        Run discovery across all available sources
        """
        
        # Ask user for search engine preference
        if self.search_engine is None:
            self.ask_search_preference()
        
        # Profile reference companies first (if any)
        reference_companies = self.criteria.get('reference_companies', [])
        if reference_companies:
            self._profile_reference_companies(reference_companies)
        
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
        elif self.search_engine == "grounding":
            # Use Google Grounding instead of Serper
            available_sources = [s for s in available_sources if s != 'google_directories']
            available_sources.append('google_grounding')

        print(f"Available sources: {', '.join(available_sources)}\n")
        
        # Run sources in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}

            if 'google_grounding' in available_sources:
                futures[executor.submit(self.discover_via_google_grounding)] = 'Google Grounding'
            elif 'google_directories' in available_sources and self.search_engine != "duckduckgo":
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
    
    def _profile_reference_companies(self, reference_companies: List[str]):
        """
        Profile reference companies to extract keywords for better searches.
        This step researches the reference companies using Grounding + Crawl4AI.
        """
        print("\n" + "="*60)
        print(" REFERENCE COMPANY PROFILING")
        print("="*60)
        print(f"\nResearching {len(reference_companies)} reference company(s) to understand")
        print("their products, industry focus, and keywords...\n")
        
        try:
            from sources.reference_profiler import ReferenceProfiler, extract_search_keywords
            
            profiler = ReferenceProfiler()
            self.reference_profiles = profiler.profile_multiple(reference_companies[:3])
            
            # Extract enhanced keywords from profiles
            self.enhanced_keywords = extract_search_keywords(self.reference_profiles)
            
            if self.enhanced_keywords:
                print(f"\n   [SUCCESS] Extracted {len(self.enhanced_keywords)} enhanced keywords:")
                for kw in self.enhanced_keywords[:8]:
                    print(f"      - {kw}")
                if len(self.enhanced_keywords) > 8:
                    print(f"      ... and {len(self.enhanced_keywords) - 8} more")
            
            print("\n" + "="*60 + "\n")
            
        except Exception as e:
            print(f"[WARNING] Reference profiling failed: {e}")
            print("Continuing with standard discovery...\n")
    
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

    def discover_via_google_grounding(self) -> List[Dict]:
        """
        Discover companies using Gemini's Google Grounding feature.
        This uses real-time web search through Gemini API.
        FREE until January 5, 2026.
        """

        print("\n[INFO] Searching with Google Grounding (Gemini real-time search)...\n")

        try:
            from sources.google_grounding import (
                search_competitors_grounded,
                search_industry_companies_grounded,
                check_google_grounding_available
            )
        except ImportError as e:
            print(f"[ERROR] google_grounding module not found: {e}")
            return []

        if not check_google_grounding_available():
            print("[ERROR] Google Grounding requires GEMINI_API_KEY")
            return []

        companies = []

        # Get criteria
        reference_companies = self.criteria.get('reference_companies', [])
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        geography = self.criteria.get('geography', {})
        regions = geography.get('regions', ['USA'])

        main_industry = industries[0] if industries else "company"
        
        # Use enhanced keywords from profiling if available
        if self.enhanced_keywords:
            keywords = list(set(keywords + self.enhanced_keywords))
            print(f"   [Enhanced] Using {len(self.enhanced_keywords)} keywords from reference profiling")

        # Phase 1: Search for competitors of reference companies
        if reference_companies:
            print(f"   [Phase 1] Searching competitors of: {', '.join(reference_companies[:3])}")
            competitor_results = search_competitors_grounded(
                reference_companies=reference_companies[:3],
                industry=main_industry,
                geography=regions
            )
            companies.extend(competitor_results)
            print(f"   Found {len(competitor_results)} from competitor search")
            time.sleep(2)

        # Phase 2: Search for industry companies
        print(f"   [Phase 2] Searching {main_industry} companies in {regions[0] if regions else 'USA'}...")
        industry_results = search_industry_companies_grounded(
            industry=main_industry,
            keywords=keywords[:5],
            geography=regions,
            size_preference="mid-market"
        )
        companies.extend(industry_results)
        print(f"   Found {len(industry_results)} from industry search")

        # Deduplicate
        seen_names = set()
        unique_companies = []
        for c in companies:
            name_lower = c.get('name', '').lower().strip()
            if name_lower and name_lower not in seen_names:
                seen_names.add(name_lower)
                unique_companies.append(c)

        print(f"\n   [Grounding] Total unique companies: {len(unique_companies)}")
        return unique_companies

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

        main_industry = industries[0] if industries else "company"

        queries = []

        # ─────────────────────────────────────────────────────────────
        # PHASE 1: Reference Company Competitors (HIGH VALUE)
        # Generate queries for ALL reference companies, not just the first
        # ─────────────────────────────────────────────────────────────
        for ref_company in reference_companies[:5]:  # Use up to 5 reference companies
            # Direct competitor queries
            queries.extend([
                f'"{ref_company}" competitors',
                f'"{ref_company}" top competitors',
                f'companies like "{ref_company}"',
                f'companies similar to {ref_company}',
                f'"{ref_company}" alternatives',
                f'best alternatives to {ref_company}',
                f'{ref_company} vs',
            ])

            # Industry-specific competitor queries
            for region in regions[:2]:
                queries.extend([
                    f'best {main_industry} companies similar to {ref_company}',
                    f'competitors of {ref_company} {region}',
                    f'{ref_company} competitors {region}',
                ])

        # Cross-reference queries (if multiple reference companies)
        if len(reference_companies) >= 2:
            ref1, ref2 = reference_companies[0], reference_companies[1]
            queries.extend([
                f'{ref1} vs {ref2} competitors',
                f'companies like {ref1} and {ref2}',
                f'{ref1} {ref2} alternatives',
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
        # Use all reference companies for comprehensive competitor discovery
        # ─────────────────────────────────────────────────────────────
        for ref_company in reference_companies[:3]:  # Top 3 reference companies
            # Top competitors queries
            queries.extend([
                f'top {ref_company} competitors',
                f'{ref_company} biggest competitors',
                f'top 10 {ref_company} competitors',
                f'{ref_company} competitor list',
            ])

            # Analysis/comparison queries
            queries.extend([
                f'{ref_company} competitor analysis',
                f'who competes with {ref_company}',
                f'{ref_company} competition',
            ])

            # Vs queries (often yield competitor lists)
            queries.extend([
                f'{ref_company} vs',
                f'alternatives to {ref_company}',
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
        
        # Log what we're using
        if reference_companies:
            print(f"\n   Using reference companies: {', '.join(reference_companies[:3])}")

        print(f"   Generated {len(unique_queries)} search queries:")
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
        Discover companies via Apollo.io API (Mixed Companies Search)
        """
        print("\n" + "─"*50)
        print("APOLLO.IO DISCOVERY")
        print("─"*50)
        
        if not self.apollo_key:
            # Try alternative env var
            self.apollo_key = os.getenv('APOLLO_API_KEY')
            
        if not self.apollo_key:
            print("   [WARNING] Apollo API key not configured (APOLLO_KEY or APOLLO_API_KEY)")
            return []

        companies = []
        url = "https://api.apollo.io/api/v1/mixed_companies/search"
        
        # Apollo requires API key in header (not body)
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': self.apollo_key
        }
        
        # Build payload from criteria (no api_key in body)
        payload = {
            "page": 1,
            "per_page": 25, # Conservative batch
            "q_organization_name": "", 
        }

        # 1. Keywords
        industry = self.criteria.get('industry', {})
        keywords = industry.get('keywords', [])
        target_industry = industry.get('industry', [])
        
        if keywords:
            # Apollo keyword search
            # We combine top 3 keywords
            payload["q_keywords"] = " ".join(keywords[:3])
            print(f"   [Apollo] Keywords: {payload['q_keywords']}")

        # 2. Location
        geo = self.criteria.get('geography', {})
        regions = geo.get('regions', [])
        countries = geo.get('countries', [])
        
        if regions or countries:
            # Apollo uses 'organization_locations'
            # We map broad regions to country codes or names if possible
            # unique_locations = list(set(regions + countries))
            # payload["organization_locations"] = unique_locations  # This requires valid Apollo location IDs or strings
            pass # Skipping exact location mapping for now to avoid zero results due to mismatch

        # 3. Revenue
        rev = self.criteria.get('revenue', {})
        # min_rev = rev.get('min_revenue_millions')
        # max_rev = rev.get('max_revenue_millions')
        # if min_rev:
             # Apollo ranges are specific strings, harder to map dynamically without lookup
             # payload["revenue_range"] = ... 
             # pass

        try:
            print(f"   [Apollo] Searching...")
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                orgs = data.get('organizations', [])
                
                print(f"   [Apollo] Found {len(orgs)} organizations")
                
                for org in orgs:
                    companies.append({
                        "name": org.get("name"),
                        "domain": org.get("domain"),
                        "website": org.get("website_url"),
                        "location": f"{org.get('city')}, {org.get('state')}, {org.get('country')}",
                        "info": org.get("short_description") or org.get("headline"),
                        "source": "apollo",
                        "fit_score": 60, # Baseline score for verified data
                        "raw_data": org # Keep full record
                    })
                    
            elif response.status_code == 422:
                 print(f"   [Apollo] Query too broad or invalid params. Response: {response.text[:200]}")
            elif response.status_code == 429:
                 print("   [Apollo] Rate limited.")
            else:
                 print(f"   [Apollo] Error {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"   [Apollo] Exception: {e}")

        return companies
    
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
        PRELIMINARY scoring during discovery phase.
        This is a QUICK relevance filter - real scoring happens after enrichment.

        We only filter out obviously irrelevant companies here.
        Detailed scoring with revenue/size happens in enrichment phase.
        """

        if not companies:
            return []

        # Get reference company info
        reference_companies = self.criteria.get('reference_companies', [])

        # Get criteria details
        industry = self.criteria.get('industry', {})
        industries = industry.get('industry', [])
        keywords = industry.get('keywords', [])
        geography = self.criteria.get('geography', {})
        regions = geography.get('regions', ['USA'])

        print(f"\n[INFO] Quick relevance filtering {len(companies)} companies...")

        if reference_companies:
            print(f"   Reference companies: {', '.join(reference_companies[:3])}")

        # Quick relevance scoring in batches
        batch_size = 15
        scored = []

        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            print(f"   Filtering batch {i//batch_size + 1}/{(len(companies) + batch_size - 1)//batch_size}...")

            try:
                batch_scored = self._quick_relevance_filter(
                    batch,
                    reference_companies,
                    industries + keywords,
                    regions
                )
                scored.extend(batch_scored)

                # Rate limit
                time.sleep(2)

            except Exception as e:
                print(f"      Filtering failed: {e}")
                # Fallback - keep all with default score
                for company in batch:
                    company['fit_score'] = 50
                    company['score_reason'] = "Pending enrichment for detailed scoring"
                    scored.append(company)

        # Sort by score
        scored.sort(key=lambda x: x.get('fit_score', 0), reverse=True)

        print(f"   Filtering complete. Kept {len([c for c in scored if c.get('fit_score', 0) >= 30])} relevant companies")

        return scored
    
    def _quick_relevance_filter(
        self,
        companies: List[Dict],
        reference_companies: List[str],
        industry_keywords: List[str],
        regions: List[str]
    ) -> List[Dict]:
        """
        Quick relevance filter during discovery.
        Only checks: Is this company in the right industry/geography?
        Does NOT try to assess revenue (that requires enrichment).
        """

        # Build company list for prompt
        company_summaries = []
        for i, c in enumerate(companies):
            summary = f"{i+1}. {c.get('name', 'Unknown')}"
            if c.get('location'):
                summary += f" | Location: {c.get('location')}"
            if c.get('info'):
                summary += f" | Info: {c.get('info', '')[:100]}"
            company_summaries.append(summary)

        company_list = "\n".join(company_summaries)

        # Build reference context
        ref_context = ""
        if reference_companies:
            ref_list = ", ".join(reference_companies[:5])
            ref_context = f"Reference companies (find similar): {ref_list}\n"

        prompt = f"""Quick relevance check for M&A target discovery.

{ref_context}Target Industry: {', '.join(industry_keywords[:5])}
Target Geography: {', '.join(regions)}

Companies to check:
{company_list}

For each company, determine RELEVANCE (not final score - that comes after enrichment):

RELEVANCE 70-100 (HIGHLY RELEVANT):
- Clearly in the target industry
- Matches geography
- Appears to be a real operating company
- Similar to reference companies

RELEVANCE 40-70 (POSSIBLY RELEVANT):
- Related industry
- Geography unclear
- Needs more research

RELEVANCE 0-40 (NOT RELEVANT):
- Wrong industry entirely (e.g., food producer vs packaging)
- Company no longer exists / was acquired
- Not a real company (association, government, etc.)
- Clearly wrong geography

NOTE: Do NOT try to assess company SIZE here. We don't have revenue data yet.
Just check industry and geography relevance.

Return JSON array:
[
  {{"company_number": 1, "score": 80, "reason": "Custom packaging company, US-based"}},
  {{"company_number": 2, "score": 20, "reason": "Food producer, not packaging manufacturer"}}
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
            
            # Create new session if not already set
            if self.session_id:
                print(f"[DB] Using existing session #{self.session_id}")
            else:
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
                    "website": c.get("website", ""),  # Strict: don't use source_url as fallback
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

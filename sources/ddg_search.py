"""
DuckDuckGo Search Fallback

Free backup when Serper quota is exhausted.
Uses ddgs library (formerly duckduckgo-search).
"""

from typing import List, Dict
import time

try:
    from duckduckgo_search import DDGS
except ImportError:
    # Try the new package name
    try:
        from ddgs import DDGS
    except ImportError:
        DDGS = None

from utils.logging import get_logger
from utils.retry import retry_api_call, RateLimiter

logger = get_logger(__name__)

# Rate limit DDG to avoid blocks (1 request per 2 seconds)
DDG_LIMITER = RateLimiter(calls_per_minute=30)


class DuckDuckGoSearch:
    """
    DuckDuckGo search as fallback when Serper quota exhausted.
    """
    
    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        
        if DDGS is None:
            logger.error("DuckDuckGo search not available. Install with: pip install duckduckgo-search")
    
    @retry_api_call(max_attempts=3, min_wait=2, max_wait=30)
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search DuckDuckGo and return results.
        
        Returns:
            List of dicts with keys: title, href, body
        """
        if DDGS is None:
            return []
            
        DDG_LIMITER.wait()
        
        logger.info("Searching DDG", query=query[:50])
        
        try:
            # DDGS returns generator, need to convert to list
            ddgs = DDGS()
            results = list(ddgs.text(
                query,
                max_results=max_results
            ))
            
            logger.info("DDG search complete", results=len(results))
            return results
            
        except Exception as e:
            logger.error("DDG search failed", error=str(e))
            return []
    
    def search_for_directories(
        self, 
        queries: List[str], 
        max_results_per_query: int = 10
    ) -> List[str]:
        """
        Search for directory pages and return URLs.
        
        Args:
            queries: List of search queries
            max_results_per_query: Max results per query
            
        Returns:
            List of URLs to scrape
        """
        all_urls = []
        
        for query in queries:
            try:
                results = self.search(query, max_results=max_results_per_query)
                
                for r in results:
                    url = r.get("href", "")
                    if url and self._is_valid_url(url):
                        all_urls.append(url)
                
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.warning("DDG query failed", query=query[:30], error=str(e))
                continue
        
        # Deduplicate
        unique_urls = list(set(all_urls))
        logger.info("Found directory URLs", total=len(unique_urls))
        
        return unique_urls
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL should be included (skip known bad domains)."""
        url_lower = url.lower()
        
        # Skip these domains
        skip_domains = [
            "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
            "youtube.com", "instagram.com", "reddit.com", "quora.com",
            "amazon.com", "ebay.com", "yelp.com", "glassdoor.com",
            "bloomberg.com", "reuters.com", "forbes.com",
        ]
        
        for domain in skip_domains:
            if domain in url_lower:
                return False
        
        return True


# Singleton instance
_ddg_search = None

def get_ddg_search() -> DuckDuckGoSearch:
    """Get singleton DDG search instance."""
    global _ddg_search
    if _ddg_search is None:
        _ddg_search = DuckDuckGoSearch()
    return _ddg_search

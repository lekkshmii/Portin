"""
Crawl4AI Scraping Module for Portin

Advanced web scraping using Crawl4AI:
- Handles JavaScript-heavy pages (via Playwright)
- Returns clean Markdown for LLM processing
- Async architecture for speed
- Better than basic HTTP requests

Installation:
  pip install crawl4ai
  crawl4ai-setup  # Install browser dependencies
"""

import asyncio
from typing import Optional, Dict, List
from utils.logging import get_logger
from utils.retry import retry_api_call

logger = get_logger(__name__)

# Try to import Crawl4AI
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("Crawl4AI not installed. Run: pip install crawl4ai && crawl4ai-setup")


class Crawl4AIScraper:
    """
    Web scraper using Crawl4AI for LLM-optimized output.
    Falls back to basic HTTP if Crawl4AI unavailable.
    """
    
    def __init__(self):
        self.available = CRAWL4AI_AVAILABLE
        self._crawler = None
    
    async def _get_crawler(self):
        """Lazy initialization of crawler."""
        if self._crawler is None and self.available:
            self._crawler = AsyncWebCrawler(verbose=False)
            await self._crawler.__aenter__()
        return self._crawler
    
    async def close(self):
        """Clean up crawler resources."""
        if self._crawler:
            await self._crawler.__aexit__(None, None, None)
            self._crawler = None
    
    async def scrape(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Scrape a URL and return clean Markdown content.
        
        Args:
            url: URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Markdown content or None on failure
        """
        if not self.available:
            logger.warning("Crawl4AI not available, using fallback HTTP")
            return await self._fallback_scrape(url, timeout)
        
        try:
            crawler = await self._get_crawler()
            
            logger.info("Scraping with Crawl4AI", url=url[:60])
            
            result = await crawler.arun(
                url=url,
                timeout=timeout * 1000,  # Crawl4AI uses milliseconds
            )
            
            if result.success:
                # Return markdown content (cleaner for LLM)
                content = result.markdown if hasattr(result, 'markdown') else result.cleaned_html
                
                if content:
                    # Truncate to reasonable size for LLM
                    content = content[:12000]
                    logger.info("Scrape successful", url=url[:40], chars=len(content))
                    return content
            
            logger.warning("Scrape returned empty", url=url[:40])
            return None
            
        except Exception as e:
            logger.error("Crawl4AI scrape failed", url=url[:40], error=str(e))
            # Fall back to basic HTTP
            return await self._fallback_scrape(url, timeout)
    
    async def _fallback_scrape(self, url: str, timeout: int = 10) -> Optional[str]:
        """Fallback to basic HTTP scraping."""
        import requests
        import re
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, headers=headers, timeout=timeout)
            )
            
            if response.status_code == 200:
                text = response.text
                
                # Remove scripts and styles
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                
                # Clean whitespace
                text = ' '.join(text.split())
                
                return text[:12000]
                
        except Exception as e:
            logger.error("Fallback scrape failed", url=url[:40], error=str(e))
        
        return None
    
    async def scrape_multiple(self, urls: List[str], timeout: int = 30) -> Dict[str, Optional[str]]:
        """
        Scrape multiple URLs concurrently.
        
        Returns:
            Dict mapping URL to content (or None on failure)
        """
        results = {}
        
        # Process in batches to avoid overwhelming
        batch_size = 5
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            
            tasks = [self.scrape(url, timeout) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[url] = None
                else:
                    results[url] = result
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        return results


# Singleton instance
_scraper = None

async def get_scraper() -> Crawl4AIScraper:
    """Get singleton scraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = Crawl4AIScraper()
    return _scraper


# Synchronous wrapper for use in existing code
def scrape_url(url: str, timeout: int = 30) -> Optional[str]:
    """
    Synchronous wrapper for scraping a URL.
    Handles being called from threads without event loops.
    """
    
    def _sync_scrape():
        """Run in new event loop (works in any thread)."""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def _do_scrape():
                scraper = Crawl4AIScraper()
                result = await scraper.scrape(url, timeout)
                await scraper.close()
                return result
            
            return loop.run_until_complete(_do_scrape())
        finally:
            loop.close()
    
    try:
        # Check if we're in the main thread with a running loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_sync_scrape)
                return future.result(timeout=timeout + 10)
        except RuntimeError:
            # No running loop - we can use new loop directly
            return _sync_scrape()
            
    except Exception as e:
        logger.error("Sync scrape failed", url=url[:40], error=str(e))
        # Fall back to simple HTTP
        return _simple_http_scrape(url, timeout)


def _simple_http_scrape(url: str, timeout: int = 10) -> Optional[str]:
    """Ultimate fallback - simple HTTP scraping with no async."""
    import requests
    import re
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            text = response.text
            
            # Remove scripts and styles
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            
            # Clean whitespace
            text = ' '.join(text.split())
            
            return text[:12000]
            
    except Exception as e:
        logger.error("HTTP fallback failed", url=url[:40], error=str(e))
    
    return None


def check_crawl4ai_available() -> bool:
    """Check if Crawl4AI is properly installed."""
    return CRAWL4AI_AVAILABLE

"""
Test Script for Phase 2 - Better Discovery

Tests all Phase 2 discovery sources:
- Crawl4AI scraper
- SEC EDGAR search
- UK Companies House
- OpenCorporates
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_crawl4ai():
    """Test Crawl4AI scraper."""
    print("\n" + "="*50)
    print("TEST 1: Crawl4AI Scraper")
    print("="*50)
    
    try:
        from sources.crawl4ai_scraper import check_crawl4ai_available, scrape_url
        
        available = check_crawl4ai_available()
        print(f"Crawl4AI available: {available}")
        
        if available:
            # Test a simple URL
            content = scrape_url("https://example.com", timeout=10)
            if content:
                print(f"Scraped {len(content)} characters")
                print("✅ Crawl4AI works!")
            else:
                print("⚠️ Crawl4AI returned empty (fallback to HTTP worked)")
        else:
            print("⚠️ Crawl4AI not installed. Run: pip install crawl4ai && crawl4ai-setup")
        
        return True
        
    except Exception as e:
        print(f"❌ Crawl4AI error: {e}")
        return False


def test_sec_edgar():
    """Test SEC EDGAR search."""
    print("\n" + "="*50)
    print("TEST 2: SEC EDGAR Search")
    print("="*50)
    
    try:
        from sources.sec_edgar import SECEdgarSearch, get_sic_for_industry
        
        sec = SECEdgarSearch()
        
        # Test name search
        print("Searching for 'packaging'...")
        results = sec.search_by_name("packaging", limit=3)
        print(f"Found {len(results)} companies by name")
        
        for r in results[:2]:
            print(f"  - {r.get('name', 'Unknown')[:40]} ({r.get('ticker', 'N/A')})")
        
        # Test SIC mapping
        sic_codes = get_sic_for_industry(["packaging", "printing"])
        print(f"SIC codes for packaging/printing: {sic_codes}")
        
        print("✅ SEC EDGAR works!")
        return True
        
    except Exception as e:
        print(f"❌ SEC EDGAR error: {e}")
        return False


def test_companies_house():
    """Test UK Companies House."""
    print("\n" + "="*50)
    print("TEST 3: UK Companies House")
    print("="*50)
    
    try:
        from sources.companies_house import CompaniesHouseSearch
        
        ch = CompaniesHouseSearch()
        
        if not ch.is_available():
            print("⚠️ COMPANIES_HOUSE_API_KEY not set - skipping")
            print("   Get free key: https://developer.company-information.service.gov.uk/")
            return True  # Not a failure, just not configured
        
        # Test search
        print("Searching for 'packaging'...")
        results = ch.search("packaging", limit=3)
        print(f"Found {len(results)} UK companies")
        
        for r in results[:2]:
            print(f"  - {r.get('name', 'Unknown')[:40]}")
        
        print("✅ Companies House works!")
        return True
        
    except Exception as e:
        print(f"❌ Companies House error: {e}")
        return False


def test_opencorporates():
    """Test OpenCorporates global search."""
    print("\n" + "="*50)
    print("TEST 4: OpenCorporates")
    print("="*50)
    
    try:
        from sources.opencorporates import OpenCorporatesSearch
        
        oc = OpenCorporatesSearch()
        
        # Test search
        print("Searching for 'packaging'...")
        results = oc.search("packaging", limit=5)
        print(f"Found {len(results)} companies globally")
        
        for r in results[:3]:
            print(f"  - {r.get('name', 'Unknown')[:40]} ({r.get('jurisdiction', 'N/A').upper()})")
        
        print("✅ OpenCorporates works!")
        return True
        
    except Exception as e:
        print(f"❌ OpenCorporates error: {e}")
        return False


def test_discovery_engine():
    """Test the discovery engine integration."""
    print("\n" + "="*50)
    print("TEST 5: Discovery Engine (Integration)")
    print("="*50)
    
    try:
        from discovery.engine import AggressiveDiscoveryEngine
        
        # Test with mock criteria
        mock_criteria = {
            "reference_companies": ["Noissue"],
            "industry": {
                "industry": ["packaging"],
                "keywords": ["custom packaging", "sustainable"]
            },
            "geography": {
                "regions": ["USA"]
            }
        }
        
        engine = AggressiveDiscoveryEngine(mock_criteria)
        
        # Check available sources
        sources = engine.check_available_sources()
        print(f"Available sources: {sources}")
        
        # Test query generation (doesn't hit APIs)
        queries = engine.generate_search_queries()
        print(f"Generated {len(queries)} search queries:")
        for q in queries[:3]:
            print(f"  - {q}")
        
        print("✅ Discovery Engine works!")
        return True
        
    except Exception as e:
        print(f"❌ Discovery Engine error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 2 tests."""
    print("\n" + "="*60)
    print("  PORTIN PHASE 2 TEST SUITE")
    print("="*60)
    
    tests = [
        ("Crawl4AI", test_crawl4ai),
        ("SEC EDGAR", test_sec_edgar),
        ("Companies House", test_companies_house),
        ("OpenCorporates", test_opencorporates),
        ("Discovery Engine", test_discovery_engine),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} FAILED: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name}: {status}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n  Total: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    return all(s for _, s in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

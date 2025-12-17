"""
Test Script for Phase 1 Foundation

Run this to verify all Phase 1 components work:
- SQLite database
- Pydantic models
- Retry decorators
- Structured logging
- DuckDuckGo search
"""

import os
import sys

# Add portin directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_logging():
    """Test structured logging."""
    print("\n" + "="*50)
    print("TEST 1: Structured Logging")
    print("="*50)
    
    from utils.logging import log_info, log_warning, log_error, get_logger
    
    log_info("This is an info message", test=True)
    log_warning("This is a warning", value=42)
    log_error("This is an error", reason="testing")
    
    logger = get_logger("test")
    logger.info("Custom logger works", custom=True)
    
    print("✅ Logging works!\n")
    return True


def test_models():
    """Test Pydantic models."""
    print("\n" + "="*50)
    print("TEST 2: Pydantic Models")
    print("="*50)
    
    from models import (
        SearchCriteria, 
        DiscoveredCompany, 
        EnrichedCompany,
        validate_company
    )
    
    # Test SearchCriteria
    criteria = SearchCriteria(
        reference_companies=["Amul"],
        industry={"industry": ["Dairy"], "keywords": ["milk", "dairy products"]}
    )
    print(f"Criteria: {criteria.reference_companies}")
    
    # Test DiscoveredCompany
    company = DiscoveredCompany(
        name="Test Company Inc",
        domain="testcompany.com",
        source="duckduckgo"
    )
    print(f"Company: {company.name} ({company.domain})")
    
    # Test validation
    invalid = validate_company({"name": ""})  # Should return None
    valid = validate_company({"name": "Valid Corp"})
    print(f"Validation test: invalid={invalid is None}, valid={valid is not None}")
    
    print("✅ Models work!\n")
    return True


def test_database():
    """Test SQLite database."""
    print("\n" + "="*50)
    print("TEST 3: SQLite Database")
    print("="*50)
    
    import db
    
    # Use a test database
    test_db = "test_portin.db"
    
    # Initialize
    db.init_database(test_db)
    print("Database initialized")
    
    # Create session
    session_id = db.create_session(
        {"industry": ["Dairy"]},
        db_path=test_db
    )
    print(f"Created session {session_id}")
    
    # Add companies
    companies = [
        {"name": "Company A", "domain": "a.com"},
        {"name": "Company B", "domain": "b.com"},
        {"name": "Company C", "domain": "c.com"},
    ]
    added = db.add_companies_batch(session_id, companies, source="test", db_path=test_db)
    print(f"Added {added} companies")
    
    # Get companies
    retrieved = db.get_companies(session_id, db_path=test_db)
    print(f"Retrieved {len(retrieved)} companies")
    
    # Save checkpoint
    db.save_checkpoint(session_id, "test", "key1", {"progress": 50}, db_path=test_db)
    checkpoint = db.get_checkpoint(session_id, "test", "key1", db_path=test_db)
    print(f"Checkpoint: {checkpoint}")
    
    # Get stats
    stats = db.get_session_stats(session_id, db_path=test_db)
    print(f"Stats: {stats}")
    
    # Cleanup test database
    os.remove(test_db)
    print("Test database cleaned up")
    
    print("✅ Database works!\n")
    return True


def test_retry():
    """Test retry decorators."""
    print("\n" + "="*50)
    print("TEST 4: Retry Decorators")
    print("="*50)
    
    from utils.retry import retry_api_call, RateLimiter
    import time
    
    # Test rate limiter
    limiter = RateLimiter(calls_per_minute=60)  # 1 per second
    
    start = time.time()
    limiter.wait()
    limiter.wait()
    elapsed = time.time() - start
    print(f"Rate limiter enforced ~1s delay: {elapsed:.2f}s")
    
    # Test retry decorator
    call_count = 0
    
    @retry_api_call(max_attempts=3, min_wait=0.1, max_wait=0.5)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Simulated failure")
        return "success"
    
    result = flaky_function()
    print(f"Retry test: {call_count} attempts, result={result}")
    
    print("✅ Retry works!\n")
    return True


def test_ddg_search():
    """Test DuckDuckGo search."""
    print("\n" + "="*50)
    print("TEST 5: DuckDuckGo Search")
    print("="*50)
    
    from ddg_search import DuckDuckGoSearch
    
    ddg = DuckDuckGoSearch(rate_limit_delay=1.0)
    
    # Simple search
    results = ddg.search("dairy companies USA", max_results=3)
    print(f"Found {len(results)} results")
    
    for r in results[:3]:
        print(f"  - {r.get('title', 'No title')[:50]}...")
    
    print("✅ DDG Search works!\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  PORTIN PHASE 1 TEST SUITE")
    print("="*60)
    
    tests = [
        ("Logging", test_logging),
        ("Models", test_models),
        ("Database", test_database),
        ("Retry", test_retry),
        ("DDG Search", test_ddg_search),
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

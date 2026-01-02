
import sys
import os

print("Running Deep Research Verification...")

try:
    # 1. Imports
    print("[1/4] Checking Imports...")
    from data.models import EnrichedCompany, VerifiedClaim, Citation, DeepResearchMetadata
    from data.db import init_database
    from enrichment.deep_research import DeepResearchEnricher
    from enrichment.screener import MultiSourceEnricher
    from discovery.engine import AggressiveDiscoveryEngine
    print("   [OK] Imports successful.")

    # 2. Database Init
    print("[2/4] Checking Database Schema...")
    init_database() # Should simulate migration if DB exists
    print("   [OK] Database initialized/migrated.")

    # 3. Class Instantiation
    print("[3/4] Checking Class Instantiation...")
    enricher = DeepResearchEnricher()
    screener = MultiSourceEnricher()
    # Mock criteria
    criteria = {"industry": {"keywords": ["test"]}, "geography": {"countries": ["USA"]}}
    engine = AggressiveDiscoveryEngine(criteria)
    print("   [OK] Classes instantiated.")

    # 4. Check Methods
    print("[4/4] Checking Method Signatures...")
    if not hasattr(enricher, 'enrich_company'): raise Exception("Missing enrich_company")
    if not hasattr(engine, 'discover_via_apollo'): raise Exception("Missing discover_via_apollo")
    print("   [OK] Critical methods found.")

    print("\n✅ VERIFICATION SUCCESSFUL: Syntax and Structure are valid.")

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ RUNTIME ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

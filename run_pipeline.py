#!/usr/bin/env python3
"""
COMPLETE M&A RESEARCH PIPELINE
End-to-end system: Interview → Discovery → Enrichment → Excel

Runs the full workflow:
1. Porto interviews you
2. Discovery engine finds companies
3. Enrichment adds all details
4. Exports professional Excel
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# Get project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def check_requirements():
    """Check and install required packages"""
    
    requirements_file = 'requirements.txt'
    
    if not os.path.exists(requirements_file):
        print(f"[WARNING] {requirements_file} not found. Checking core packages manually...")
        # Fallback to manual check if requirements.txt is missing
        required = {
            'google-generativeai': 'google.generativeai',
            'google-genai': 'google.genai',
            'requests': 'requests',
            'openpyxl': 'openpyxl',
            'python-dotenv': 'dotenv'
        }
        
        missing = []
        for package, import_name in required.items():
            try:
                if '.' in import_name:
                    top_level = import_name.split('.')[0]
                    __import__(top_level)
                else:
                    __import__(import_name)
            except ImportError:
                missing.append(package)
        
        if missing:
            print("[ERROR] Missing required packages:")
            for pkg in missing:
                print(f"   - {pkg}")
            print("\nInstall with:")
            print(f"   pip install {' '.join(missing)}")
            return False
        return True

    # Auto-install from requirements.txt
    print("Checking dependencies...")
    try:
        # Check if all requirements are satisfied
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file], 
                              stdout=subprocess.DEVNULL, 
                              stderr=subprocess.DEVNULL)
        print("[OK] Dependencies installed/verified")
        return True
    except subprocess.CalledProcessError:
        print("\n[WARNING] Auto-install failed. Trying to install visibly...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
            print("[OK] Dependencies installed")
            return True
        except Exception as e:
            print(f"\n[ERROR] Could not install dependencies: {e}")
            print(f"Please run: pip install -r {requirements_file}")
            return False

def check_api_keys():
    """Check which API keys are configured"""
    
    from dotenv import load_dotenv
    load_dotenv()
    
    keys = {
        'GEMINI_API_KEY': 'Gemini (REQUIRED)',
        'SERPER_KEY': 'Serper (recommended)',
        'FIRECRAWL_KEY': 'Firecrawl (optional)',
        'APOLLO_KEY': 'Apollo (optional)'
    }
    
    print("\n🔑 API Key Status:")
    
    all_good = True
    for key, name in keys.items():
        status = "[OK]" if os.getenv(key) else "[MISSING]"
        print(f"   {status} {name}")
        
        if key == 'GEMINI_API_KEY' and not os.getenv(key):
            all_good = False
    
    if not all_good:
        print("\n[WARNING] GEMINI_API_KEY is required!")
        print("   Get free key: https://aistudio.google.com/app/apikey")
        return False
    
    print()
    return True

def run_step(step_name, script_name):
    """Run a step and handle errors"""
    
    print("\n" + "="*70)
    print(f"  STEP: {step_name}")
    print("="*70 + "\n")
    
    result = subprocess.run([sys.executable, script_name], capture_output=False)
    
    if result.returncode != 0:
        print(f"\n[ERROR] Error in {step_name}")
        return False
    
    return True

def main():
    """
    Run the complete pipeline
    """
    
    print("""
==================================================================
         COMPLETE M&A RESEARCH PIPELINE
         End-to-End Company Discovery & Enrichment
==================================================================
    """)
    
    print("This will run the complete workflow:\n")
    print("  1. Porto -> Understand your criteria")
    print("  2. Discovery Engine -> Find matching companies")
    print("  3. Enrichment System -> Add complete details")
    print("  4. Export -> Professional Excel output\n")
    
    # Pre-flight checks
    print("Running pre-flight checks...\n")
    
    if not check_requirements():
        return
    
    if not check_api_keys():
        return
    
    # Model selection
    from config.model_config import ask_model_preference
    ask_model_preference()
    
    input("Press ENTER to start the pipeline... ")
    
    # Step 1: Consultation
    if not run_step("Porto's On its way", "run_intake.py"):
        return
    
    # Check if we got criteria
    criteria_file = os.path.join(PROJECT_ROOT, 'output', 'search_criteria.json')
    if not os.path.exists(criteria_file):
        print("\n[ERROR] No search criteria generated")
        return
    
    # Step 2: Discovery
    print("\n" + "="*70)
    print("  Would you like to run company discovery?")
    print("="*70)
    print("\nThis will search across multiple sources to find companies.")
    print("It may take 5-10 minutes depending on sources available.\n")
    
    choice = input("Run discovery? (yes/no): ").lower().strip()
    
    if choice in ['y', 'yes']:
        if not run_step("COMPANY DISCOVERY", "run_discovery.py"):
            print("\n[WARNING] Discovery had issues, but continuing...")
    else:
        print("\n[SKIP] Skipping discovery")
    
    # Step 3: Enrichment
    print("\n" + "="*70)
    print("  Would you like to run enrichment?")
    print("="*70)
    print("\nThis will enrich discovered companies with full details.")
    print("Time: ~2-3 minutes per company\n")
    
    # Load discovered companies
    discovered_file = os.path.join(PROJECT_ROOT, 'output', 'discovered_companies.json')
    if os.path.exists(discovered_file):
        with open(discovered_file, 'r') as f:
            data = json.load(f)
            num_companies = len(data.get('companies', []))
        
        print(f"Found {num_companies} companies to enrich")
        print(f"Estimated time: {num_companies * 2} minutes\n")
        
        choice = input("Run enrichment? (yes/no): ").lower().strip()
        
        if choice in ['y', 'yes']:
            # Create a modified version of enricher that reads from discovered_companies.json
            if not run_step("DATA ENRICHMENT", "run_enrichment.py"):
                print("\n[WARNING] Enrichment had issues")
        else:
            print("\n[SKIP] Skipping enrichment")
    else:
        print("\n[WARNING] No discovered companies file found")
        print("You can run enrichment manually later")
    
    # Summary
    print("\n\n" + "="*70)
    print("  PIPELINE COMPLETE")
    print("="*70)
    
    print("\nGenerated files:")
    
    files = [
        (os.path.join('output', 'search_criteria.json'), 'Your search criteria'),
        (os.path.join('output', 'discovered_companies.json'), 'Discovered companies'),
        (os.path.join('exports', 'MA_Screening_Demo.xlsx'), 'Enriched companies Excel')
    ]
    
    for filepath, description in files:
        full_path = os.path.join(PROJECT_ROOT, filepath)
        if os.path.exists(full_path):
            print(f"   [OK] {filepath} - {description}")
        else:
            print(f"   [SKIP] {filepath} - {description} (skipped)")
    
    print("\n" + "="*70)
    print("\nWhat's next?")
    print("  • Review the Excel file")
    print("  • Analyze the discovered companies")
    print("  • Re-run discovery with different criteria")
    print("  • Run enrichment on more companies")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARNING] Pipeline interrupted by user")
        sys.exit(0)

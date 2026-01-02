#!/usr/bin/env python3
"""
DATABASE MAINTENANCE UTILITY
Re-score companies and add industry tags using Gemini

Features:
- Re-score companies based on a reference company
- Add/update industry tags for companies
- User can provide tags or let Gemini auto-tag
"""

import os
import json
import time
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from config.model_config import get_current_model

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


class DatabaseMaintenance:
    """Utility for maintaining and updating company database."""
    
    def __init__(self):
        self.gemini = genai.GenerativeModel(get_current_model())
        self.last_call = 0
        self.min_interval = 3  # seconds between Gemini calls
    
    def _rate_limit(self):
        """Rate limit Gemini calls."""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
    
    def score_companies_with_gemini(
        self,
        companies: List[Dict],
        reference_company: str,
        industry: str,
        batch_size: int = 10
    ) -> List[Dict]:
        """
        Score companies based on similarity to a reference company.
        Returns companies with updated scores.
        """
        
        scored = []
        total_batches = (len(companies) + batch_size - 1) // batch_size
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            batch_num = i // batch_size + 1
            print(f"   Scoring batch {batch_num}/{total_batches}...")
            
            self._rate_limit()
            
            company_list = "\n".join([
                f"- {c.get('name', 'Unknown')}: {c.get('info', c.get('raw_data_json', ''))[:100]}"
                for c in batch
            ])
            
            prompt = f"""Score these companies for M&A fit with the reference company.

REFERENCE COMPANY: {reference_company}
INDUSTRY: {industry}

Score each company 0-100 based on:
- Industry relevance (how closely they match the reference industry)
- Size compatibility (similar scale/market position)
- Geographic fit
- Strategic synergy potential

COMPANIES TO SCORE:
{company_list}

Return ONLY a JSON array with company names and scores:
[{{"name": "Company A", "score": 85, "reason": "Strong industry match"}}, ...]"""

            try:
                response = self.gemini.generate_content(prompt)
                text = response.text.strip()
                
                # Parse JSON
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0].strip()
                
                scores = json.loads(text)
                score_map = {s['name'].lower(): s for s in scores}
                
                # Update companies with scores
                for c in batch:
                    name_lower = c.get('name', '').lower()
                    if name_lower in score_map:
                        c['score'] = score_map[name_lower].get('score', 50)
                        c['score_reason'] = score_map[name_lower].get('reason', '')
                    else:
                        c['score'] = 50  # Default
                    scored.append(c)
                    
            except Exception as e:
                print(f"      [WARNING] Scoring failed: {e}")
                for c in batch:
                    c['score'] = 50
                    scored.append(c)
        
        return scored
    
    def tag_companies_with_gemini(
        self,
        companies: List[Dict],
        batch_size: int = 15
    ) -> List[Dict]:
        """
        Add industry tags to companies using Gemini.
        """
        
        tagged = []
        total_batches = (len(companies) + batch_size - 1) // batch_size
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            batch_num = i // batch_size + 1
            print(f"   Tagging batch {batch_num}/{total_batches}...")
            
            self._rate_limit()
            
            company_list = "\n".join([
                f"- {c.get('name', 'Unknown')}"
                for c in batch
            ])
            
            prompt = f"""Identify the primary industry for each company.

COMPANIES:
{company_list}

For each company, provide a short industry tag (1-3 words) like:
- Packaging
- Food Service
- Industrial Supplies
- Custom Printing
- Promotional Products
- Paper Products
- Sustainable Packaging

Return ONLY a JSON array:
[{{"name": "Company A", "industry": "Packaging"}}, ...]"""

            try:
                response = self.gemini.generate_content(prompt)
                text = response.text.strip()
                
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0].strip()
                
                tags = json.loads(text)
                tag_map = {t['name'].lower(): t.get('industry', 'Unknown') for t in tags}
                
                for c in batch:
                    name_lower = c.get('name', '').lower()
                    c['industry_tag'] = tag_map.get(name_lower, 'Unknown')
                    tagged.append(c)
                    
            except Exception as e:
                print(f"      [WARNING] Tagging failed: {e}")
                for c in batch:
                    c['industry_tag'] = 'Unknown'
                    tagged.append(c)
        
        return tagged


def main():
    """Main menu for database maintenance."""
    
    print("=" * 60)
    print(" DATABASE MAINTENANCE UTILITY")
    print("=" * 60)
    
    # Check API key
    if not os.getenv('GEMINI_API_KEY'):
        print("\n[ERROR] GEMINI_API_KEY required!")
        return
    
    # Check database
    try:
        from data.db import get_db_connection, get_database_stats, get_all_sessions, DB_PATH
        import os as os_module
        
        if not os_module.path.exists(DB_PATH):
            print("\n[ERROR] No database found! Run discovery first.")
            return
        
        stats = get_database_stats()
        print(f"\n[DB] Current Status:")
        print(f"     Total companies: {stats['unique_companies']}")
        print(f"     With scores: {stats.get('discovered', 0) + stats.get('enriched', 0)}")
        
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")
        return
    
    # Menu
    print("\n" + "─"*50)
    print("OPTIONS")
    print("─"*50)
    print("\n[1] Re-score all companies with Gemini")
    print("[2] Add industry tags to companies")
    print("[3] Both (score + tag)")
    print("[4] View current scores")
    print("[5] Exit")
    
    choice = input("\nSelect option [1-5]: ").strip()
    
    if choice == "5" or not choice:
        return
    
    if choice == "4":
        # Show current scores
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, score FROM companies 
                WHERE score IS NOT NULL 
                ORDER BY score DESC LIMIT 20
            """)
            rows = cursor.fetchall()
            
            print("\nTop 20 Companies by Score:")
            print("-" * 50)
            for row in rows:
                print(f"  {row[0][:35]:35} | Score: {row[1]}")
        return
    
    # Get reference company for scoring
    reference_company = ""
    industry = ""
    
    if choice in ["1", "3"]:
        print("\n" + "─"*50)
        print("SCORING SETUP")
        print("─"*50)
        reference_company = input("\nReference company (e.g., PakFactory): ").strip()
        if not reference_company:
            reference_company = "PakFactory"
        
        industry = input("Industry (e.g., custom packaging): ").strip()
        if not industry:
            industry = "custom packaging"
        
        print(f"\n[OK] Will score based on: {reference_company} ({industry})")
    
    # Load companies
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, domain, website, score, raw_data_json
            FROM companies
            ORDER BY id
        """)
        companies = [dict(row) for row in cursor.fetchall()]
    
    print(f"\n[INFO] Processing {len(companies)} companies...")
    
    maintenance = DatabaseMaintenance()
    
    # Process based on choice
    if choice == "1":
        # Score only
        companies = maintenance.score_companies_with_gemini(
            companies, reference_company, industry
        )
        
    elif choice == "2":
        # Tag only - ask user first
        print("\n" + "─"*50)
        print("TAGGING OPTIONS")
        print("─"*50)
        print("\n[1] Let Gemini auto-tag all companies")
        print("[2] Manually enter a tag for all companies")
        
        tag_choice = input("\nSelect [1/2]: ").strip()
        
        if tag_choice == "2":
            manual_tag = input("Enter industry tag (e.g., Packaging): ").strip()
            for c in companies:
                c['industry_tag'] = manual_tag
        else:
            companies = maintenance.tag_companies_with_gemini(companies)
            
    elif choice == "3":
        # Both
        print("\n[STEP 1/2] Scoring...")
        companies = maintenance.score_companies_with_gemini(
            companies, reference_company, industry
        )
        print("\n[STEP 2/2] Tagging...")
        companies = maintenance.tag_companies_with_gemini(companies)
    
    # Save back to database
    print("\n[INFO] Saving to database...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updated = 0
        
        for c in companies:
            try:
                # Update score and/or industry tag
                if 'score' in c and c['score'] is not None:
                    cursor.execute(
                        "UPDATE companies SET score = ? WHERE id = ?",
                        (c['score'], c['id'])
                    )
                    updated += 1
                    
            except Exception as e:
                print(f"   [WARNING] Failed to update {c.get('name')}: {e}")
    
    print(f"\n[SUCCESS] Updated {updated} companies!")
    
    # Show top scores
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, score FROM companies 
            WHERE score IS NOT NULL 
            ORDER BY score DESC LIMIT 10
        """)
        rows = cursor.fetchall()
        
        print("\nTop 10 Companies by Score:")
        print("-" * 50)
        for row in rows:
            print(f"  {row[0][:35]:35} | Score: {row[1]}")


if __name__ == "__main__":
    main()

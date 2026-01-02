"""
Reference Company Profiler

Profiles reference companies to extract:
- Products and services
- Industry focus
- Target market
- Keywords for better search queries

Uses:
- Google Grounding for company research
- Crawl4AI for website scraping
- Gemini for extraction
"""

import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Import Gemini
import google.generativeai as genai
from config.model_config import get_current_model

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


class ReferenceProfiler:
    """
    Profiles reference companies to understand their products,
    industry focus, and keywords for better competitor searches.
    """
    
    def __init__(self):
        self.gemini = genai.GenerativeModel(get_current_model())
    
    def profile_company(self, company_name: str) -> Dict:
        """
        Profile a reference company using Grounding + Crawl4AI.
        
        Returns:
            Dict with company profile including products, industry, keywords
        """
        print(f"\n   [Profiling] Researching {company_name}...")
        
        profile = {
            "name": company_name,
            "website": None,
            "products": [],
            "industry_focus": [],
            "target_market": [],
            "keywords": [],
            "description": "",
            "raw_info": ""
        }
        
        # Step 1: Use Grounding to get company info
        grounding_info = self._search_with_grounding(company_name)
        if grounding_info:
            profile["raw_info"] = grounding_info
            profile["website"] = self._extract_website(grounding_info, company_name)
        
        # Step 2: Scrape website if found
        website_content = None
        if profile["website"]:
            website_content = self._scrape_website(profile["website"])
        
        # Step 3: Extract structured profile using Gemini
        extracted = self._extract_profile(company_name, grounding_info, website_content)
        if extracted:
            profile.update(extracted)
        
        # Print summary
        self._print_profile_summary(profile)
        
        return profile
    
    def profile_multiple(self, company_names: List[str]) -> List[Dict]:
        """Profile multiple reference companies."""
        profiles = []
        for name in company_names:
            try:
                profile = self.profile_company(name)
                profiles.append(profile)
            except Exception as e:
                print(f"   [WARNING] Failed to profile {name}: {e}")
        return profiles
    
    def _search_with_grounding(self, company_name: str) -> Optional[str]:
        """Use Google Grounding to search for company information."""
        try:
            # Try new SDK first
            from google import genai as genai_new
            from google.genai import types
            
            client = genai_new.Client(api_key=os.getenv('GEMINI_API_KEY'))
            
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            
            config = types.GenerateContentConfig(
                tools=[grounding_tool]
            )
            
            prompt = f"""Research the company "{company_name}" and provide:
1. What products or services do they offer?
2. What industry are they in?
3. Who is their target market?
4. What is their website URL?
5. Key features or differentiators

Be specific and detailed about their product offerings."""
            
            response = client.models.generate_content(
                model=get_current_model(),
                contents=prompt,
                config=config
            )
            
            return response.text
            
        except Exception as e:
            print(f"   [WARNING] Grounding search failed: {e}")
            # Fallback to regular Gemini (without grounding)
            try:
                response = self.gemini.generate_content(
                    f"What products and services does {company_name} offer? What industry are they in?"
                )
                return response.text
            except:
                return None
    
    def _extract_website(self, text: str, company_name: str) -> Optional[str]:
        """Extract company website from text."""
        # Common patterns
        patterns = [
            r'(?:website|site|url)[:\s]+(?:https?://)?([a-zA-Z0-9.-]+\.[a-z]{2,})',
            r'(?:https?://)?(?:www\.)?([a-zA-Z0-9.-]+\.(com|io|co|net|org))',
        ]
        
        # Try to find website in text
        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                for match in matches:
                    domain = match if isinstance(match, str) else match[0]
                    # Filter out common non-company domains
                    if domain and not any(x in domain for x in ['google', 'wikipedia', 'linkedin', 'facebook']):
                        if not domain.startswith('http'):
                            domain = 'https://' + domain
                        return domain
        
        # Construct likely website from company name
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
        return f"https://www.{clean_name}.com"
    
    def _scrape_website(self, url: str) -> Optional[str]:
        """Scrape company website using Crawl4AI."""
        try:
            from sources.crawl4ai_scraper import scrape_url
            
            print(f"   [Profiling] Scraping website: {url}")
            content = scrape_url(url, timeout=15)
            
            if content and len(content) > 100:
                # Limit content length for Gemini
                return content[:8000]
            return None
            
        except Exception as e:
            print(f"   [WARNING] Failed to scrape {url}: {e}")
            return None
    
    def _extract_profile(
        self, 
        company_name: str, 
        grounding_info: Optional[str],
        website_content: Optional[str]
    ) -> Optional[Dict]:
        """Use Gemini to extract structured profile from gathered info."""
        
        context_parts = []
        if grounding_info:
            context_parts.append(f"Search results:\n{grounding_info}")
        if website_content:
            context_parts.append(f"Website content:\n{website_content[:4000]}")
        
        if not context_parts:
            return None
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Based on this information about {company_name}, extract a structured profile.

{context}

Return a JSON object with these fields:
{{
    "products": ["list of specific products/services they offer"],
    "industry_focus": ["specific industry niches they serve"],
    "target_market": ["types of customers they target"],
    "keywords": ["important keywords that describe their business"],
    "description": "one paragraph summary of the company"
}}

Be specific. For products, list actual product types (e.g., "custom mailer boxes", "product labels").
For industry focus, be specific (e.g., "e-commerce packaging", "food packaging").
For keywords, include terms useful for finding similar companies.

Return ONLY valid JSON, no markdown."""

        try:
            response = self.gemini.generate_content(prompt)
            text = response.text.strip()
            
            # Clean up response
            if text.startswith('```'):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            
            return json.loads(text)
            
        except Exception as e:
            print(f"   [WARNING] Profile extraction failed: {e}")
            return None
    
    def _print_profile_summary(self, profile: Dict):
        """Print a summary of the extracted profile."""
        print(f"\n   [Profile] {profile['name']}")
        
        if profile.get('products'):
            print(f"      Products: {', '.join(profile['products'][:5])}")
        
        if profile.get('industry_focus'):
            print(f"      Industry: {', '.join(profile['industry_focus'][:3])}")
        
        if profile.get('target_market'):
            print(f"      Target: {', '.join(profile['target_market'][:3])}")
        
        if profile.get('keywords'):
            print(f"      Keywords: {', '.join(profile['keywords'][:5])}")


def extract_search_keywords(profiles: List[Dict]) -> List[str]:
    """
    Extract enhanced search keywords from reference company profiles.
    Returns a list of keywords to use in competitor searches.
    """
    keywords = set()
    
    for profile in profiles:
        # Add products as keywords
        for product in profile.get('products', []):
            keywords.add(product.lower())
        
        # Add industry focus
        for industry in profile.get('industry_focus', []):
            keywords.add(industry.lower())
        
        # Add explicit keywords
        for kw in profile.get('keywords', []):
            keywords.add(kw.lower())
    
    # Filter out too generic keywords
    generic = {'company', 'business', 'service', 'product', 'solution', 'the', 'and', 'for'}
    keywords = [k for k in keywords if k not in generic and len(k) > 2]
    
    return list(keywords)[:15]  # Limit to top 15


# Quick test
if __name__ == "__main__":
    print("\n" + "="*60)
    print(" REFERENCE COMPANY PROFILER TEST")
    print("="*60 + "\n")
    
    profiler = ReferenceProfiler()
    
    # Test with a known company
    profile = profiler.profile_company("Packlane")
    
    print("\n" + "-"*40)
    print("EXTRACTED KEYWORDS:")
    keywords = extract_search_keywords([profile])
    for kw in keywords:
        print(f"  - {kw}")

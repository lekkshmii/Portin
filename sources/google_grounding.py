#!/usr/bin/env python3
"""
GOOGLE GROUNDING SEARCH
Uses Gemini's Grounding with Google Search feature for real-time web search.
FREE until January 5, 2026 for Gemini 3 models.

This provides:
- Real-time web search results
- Cited sources with URLs
- More accurate and up-to-date information than static knowledge

Supports both:
- google-genai (new SDK) - preferred for grounding
- google-generativeai (old SDK) - fallback without grounding metadata
"""

import os
import json
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from config.model_config import get_current_model

load_dotenv()

# Check which SDK is available
_USE_NEW_SDK = False
try:
    from google import genai
    from google.genai import types
    _USE_NEW_SDK = True
except ImportError:
    pass


def check_google_grounding_available() -> bool:
    """Check if Google Grounding is available (requires Gemini API key)."""
    return bool(os.getenv('GEMINI_API_KEY'))


def search_with_grounding(
    query: str,
    extract_companies: bool = True,
    industry_filter: List[str] = None,
    geography_filter: List[str] = None
) -> Dict:
    """
    Search using Gemini with Google Grounding.

    Args:
        query: Search query string
        extract_companies: If True, extract company names from results
        industry_filter: List of industries to filter for
        geography_filter: List of regions/countries to filter for

    Returns:
        Dict with 'companies', 'sources', 'raw_response'
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {"companies": [], "sources": [], "error": "GEMINI_API_KEY not set"}

    # Try new SDK first (has proper grounding support)
    if _USE_NEW_SDK:
        return _search_with_new_sdk(query, extract_companies, industry_filter, geography_filter)
    else:
        # Fallback to old SDK (limited grounding support)
        return _search_with_old_sdk(query, extract_companies, industry_filter, geography_filter)


def _search_with_new_sdk(
    query: str,
    extract_companies: bool,
    industry_filter: List[str],
    geography_filter: List[str]
) -> Dict:
    """Use the new google-genai SDK with proper grounding support."""
    try:
        from google import genai
        from google.genai import types

        api_key = os.getenv('GEMINI_API_KEY')
        client = genai.Client(api_key=api_key)

        # Configure grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )

        # Build the prompt
        filter_context = ""
        if industry_filter:
            filter_context += f"\nTarget industries: {', '.join(industry_filter[:5])}"
        if geography_filter:
            filter_context += f"\nTarget geography: {', '.join(geography_filter[:3])}"

        if extract_companies:
            prompt = f"""Search for: {query}
{filter_context}

Find and list company names that match this search. For each company found:
1. Company name
2. Brief description (1 sentence)
3. Location if mentioned

Focus on finding actual companies, not news articles or general information.
List as many relevant companies as you can find from the search results."""
        else:
            prompt = query

        # Make the grounded search request
        response = client.models.generate_content(
            model=get_current_model(),
            contents=prompt,
            config=config
        )

        # Extract grounding metadata
        sources = []
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                metadata = candidate.grounding_metadata

                if hasattr(metadata, 'web_search_queries'):
                    for q in metadata.web_search_queries:
                        print(f"   [Grounding] Search: {q}")

                if hasattr(metadata, 'grounding_chunks'):
                    for chunk in metadata.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append({
                                'url': chunk.web.uri,
                                'title': chunk.web.title
                            })

        # Parse companies from response
        companies = []
        if extract_companies and response.text:
            companies = _extract_companies_from_grounded_response(
                response.text, sources, industry_filter, geography_filter
            )

        return {
            "companies": companies,
            "sources": sources,
            "raw_response": response.text,
            "query": query
        }

    except Exception as e:
        print(f"[ERROR] Google Grounding (new SDK) failed: {e}")
        # Try fallback to old SDK
        return _search_with_old_sdk(query, extract_companies, industry_filter, geography_filter)


def _search_with_old_sdk(
    query: str,
    extract_companies: bool,
    industry_filter: List[str],
    geography_filter: List[str]
) -> Dict:
    """Fallback using google-generativeai SDK (no grounding metadata, but still works)."""
    try:
        import google.generativeai as genai

        api_key = os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=api_key)

        # Use configured model with google_search tool
        model = genai.GenerativeModel(
            get_current_model(),
            tools=[{"google_search": {}}]
        )

        # Build the prompt
        filter_context = ""
        if industry_filter:
            filter_context += f"\nTarget industries: {', '.join(industry_filter[:5])}"
        if geography_filter:
            filter_context += f"\nTarget geography: {', '.join(geography_filter[:3])}"

        if extract_companies:
            prompt = f"""Search the web for: {query}
{filter_context}

Find and list company names that match this search. For each company found:
1. Company name
2. Brief description (1 sentence)
3. Location if mentioned

Focus on finding actual companies. List as many relevant companies as you can find."""
        else:
            prompt = query

        response = model.generate_content(prompt)

        # Old SDK doesn't expose grounding metadata as easily
        sources = []

        # Parse companies from response
        companies = []
        if extract_companies and response.text:
            companies = _extract_companies_from_grounded_response(
                response.text, sources, industry_filter, geography_filter
            )

        return {
            "companies": companies,
            "sources": sources,
            "raw_response": response.text,
            "query": query
        }

    except Exception as e:
        print(f"[ERROR] Google Grounding (old SDK) failed: {e}")
        return {"companies": [], "sources": [], "error": str(e)}


def _extract_companies_from_grounded_response(
    text: str,
    sources: List[Dict],
    industry_filter: List[str] = None,
    geography_filter: List[str] = None
) -> List[Dict]:
    """
    Extract company information from grounded response text.
    Uses a second Gemini call to structure the data.
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        model = genai.GenerativeModel(get_current_model())

        # Build source URLs string for context
        source_urls = "\n".join([f"- {s.get('title', '')}: {s.get('url', '')}" for s in sources[:10]])

        prompt = f"""Extract company names from this search result text.

Search Result:
{text[:3000]}

Source URLs:
{source_urls}

For each company mentioned, extract:
- name: Company name
- location: City/State/Country if mentioned
- info: Brief description
- source_url: Best matching URL from the sources above

Return as JSON array:
[
  {{"name": "Company A", "location": "City, State", "info": "Brief description", "source_url": "https://..."}},
  ...
]

Only include actual companies, not:
- Industry associations
- Government agencies
- Generic terms
- News outlets

JSON only:"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Clean JSON from markdown
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()

        companies = json.loads(result_text)

        # Add discovery source tag
        for company in companies:
            company['discovery_source'] = 'Google Grounding'

        return companies if isinstance(companies, list) else []

    except Exception as e:
        print(f"   [WARNING] Company extraction failed: {e}")
        return []


def search_competitors_grounded(
    reference_companies: List[str],
    industry: str,
    geography: List[str] = None
) -> List[Dict]:
    """
    Search for competitors of reference companies using Google Grounding.

    Args:
        reference_companies: List of reference company names
        industry: Target industry
        geography: List of target regions

    Returns:
        List of discovered companies
    """
    all_companies = []
    seen_names = set()

    for ref_company in reference_companies[:3]:
        print(f"\n   [Grounding] Searching competitors of {ref_company}...")

        # Query 1: Direct competitors
        query1 = f"Who are the main competitors of {ref_company}? List {industry} companies that compete with {ref_company}."
        result1 = search_with_grounding(
            query1,
            extract_companies=True,
            industry_filter=[industry],
            geography_filter=geography
        )

        for company in result1.get('companies', []):
            name_lower = company.get('name', '').lower()
            if name_lower and name_lower not in seen_names:
                seen_names.add(name_lower)
                all_companies.append(company)

        time.sleep(2)  # Rate limit

        # Query 2: Similar companies
        query2 = f"Companies similar to {ref_company} in the {industry} industry"
        if geography:
            query2 += f" in {geography[0]}"

        result2 = search_with_grounding(
            query2,
            extract_companies=True,
            industry_filter=[industry],
            geography_filter=geography
        )

        for company in result2.get('companies', []):
            name_lower = company.get('name', '').lower()
            if name_lower and name_lower not in seen_names:
                seen_names.add(name_lower)
                all_companies.append(company)

        time.sleep(2)  # Rate limit

    print(f"   [Grounding] Found {len(all_companies)} unique companies")
    return all_companies


def search_industry_companies_grounded(
    industry: str,
    keywords: List[str],
    geography: List[str] = None,
    size_preference: str = "mid-market"
) -> List[Dict]:
    """
    Search for companies in an industry using Google Grounding.

    Args:
        industry: Target industry name
        keywords: Industry keywords
        geography: Target regions
        size_preference: "small", "mid-market", "large", or "any"

    Returns:
        List of discovered companies
    """
    all_companies = []
    seen_names = set()

    # Build queries based on criteria
    queries = []

    # Main industry query
    geo_str = geography[0] if geography else "USA"
    queries.append(f"List of {industry} companies in {geo_str}")

    # Size-specific query
    if size_preference == "mid-market":
        queries.append(f"Private {industry} companies {geo_str} mid-size")
    elif size_preference == "small":
        queries.append(f"Small {industry} startups {geo_str}")

    # Keyword-based queries
    for keyword in keywords[:2]:
        queries.append(f"Top {keyword} companies {geo_str}")

    for query in queries:
        print(f"   [Grounding] {query[:50]}...")

        result = search_with_grounding(
            query,
            extract_companies=True,
            industry_filter=[industry] + keywords[:3],
            geography_filter=geography
        )

        for company in result.get('companies', []):
            name_lower = company.get('name', '').lower()
            if name_lower and name_lower not in seen_names:
                seen_names.add(name_lower)
                all_companies.append(company)

        time.sleep(2)  # Rate limit

    print(f"   [Grounding] Found {len(all_companies)} unique companies")
    return all_companies



class GoogleGroundingSearch:
    """Class wrapper for Google Grounding Search."""
    def __init__(self):
        self.enabled = check_google_grounding_available()
        self.call_count = 0  # Track grounding calls

    def search(self, query: str) -> str:
        """
        Perform a search and return a summary string.
        """
        if not self.enabled:
            return ""
        
        self.call_count += 1  # Track API calls
        result = search_with_grounding(query, extract_companies=False)
        
        # Format the result as a string
        output = []
        if result.get('raw_response'):
             output.append(result['raw_response'])
        
        # Add sources
        sources = result.get('sources', [])
        if sources:
            output.append("\nSources:")
            for s in sources:
                output.append(f"- {s.get('title', 'Unknown')}: {s.get('url', '')}")
                
        return "\n".join(output)

# Test function
if __name__ == "__main__":
    print("Testing Google Grounding Search...")

    if not check_google_grounding_available():
        print("[ERROR] GEMINI_API_KEY not set")
        exit(1)

    # Test basic search
    result = search_with_grounding(
        "Who are the main competitors of Packlane in custom packaging?",
        extract_companies=True,
        industry_filter=["custom packaging", "packaging"],
        geography_filter=["USA", "North America"]
    )

    print(f"\nFound {len(result.get('companies', []))} companies:")
    for c in result.get('companies', [])[:5]:
        print(f"  - {c.get('name')}: {c.get('info', '')[:50]}")

    print(f"\nSources used: {len(result.get('sources', []))}")
    for s in result.get('sources', [])[:3]:
        print(f"  - {s.get('title', 'Unknown')}")

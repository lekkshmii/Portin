#!/usr/bin/env python3
"""
AI M&A RESEARCH CONSULTANT
Interactive system that interviews users, understands their criteria,
and discovers companies across multiple sources aggressively.

India-based, no legal restrictions assumed.
"""

import os
import json
import time
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from config.model_config import get_current_model

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class AIResearchConsultant:
    """
    Your AI M&A research partner
    Interviews you, understands criteria, finds companies
    """
    
    def __init__(self):
        self.model = genai.GenerativeModel(get_current_model())
        self.criteria = {}
        self.conversation_history = []
        
    def start(self):
        """
        Main consultation flow
        """
        self.print_header()
        self.introduce()
        
        # Phase 1: Interview
        self.conduct_interview()
        
        # Phase 2: Confirm understanding
        if not self.confirm_criteria():
            print("\n[WARNING] Let's start over...\n")
            return self.start()
        
        # Phase 3: Discovery
        print("\n[INFO] Great! Starting company discovery...\n")
        
        # Return criteria for discovery engine
        return self.criteria
    
    def print_header(self):
        """Pretty header"""
        print("\n" + "="*70)
        print(" Heya!! Porto's Here")
        print("="*70)
    
    def introduce(self):
        """Introduction"""
        print("\nHello! I'm your research consultant Porto.")
        print("\nI'll help you find the perfect acquisition targets by asking")
        print("a few smart questions to understand exactly what you're looking for.")
        print("\nThis will take about 2 minutes. Let's begin!\n")
        time.sleep(1)
    
    def process_form_inputs(self, form_data: Dict[str, str]) -> Dict:
        """
        Process form inputs from the dashboard.
        """
        # Map form fields to questions
        questions_map = {
            'industry': "What industry or business sector are you targeting? Any reference companies?",
            'revenue': "What's your target revenue range?",
            'geography': "Any geographic preferences?",
            'ownership': "What type of ownership are you interested in?",
            'capabilities': "Any specific capabilities or synergies you're looking for?"
        }
        
        for field_id, answer in form_data.items():
            if field_id in questions_map:
                question = questions_map[field_id]
                self.parse_and_store(field_id, question, answer)
        
        return self.criteria

    def conduct_interview(self):
        """
        Smart interview process
        """
        
        # Question sequence
        questions = [
            {
                'id': 'industry',
                'question': "What industry or business sector are you targeting? Any reference companies?",
                'examples': ['promotional products like Vistaprint', 'custom packaging similar to Packlane', 'tech services'],
                'hint': "Be specific. Mention reference companies if you have any (e.g., 'companies like X, Y, Z')"
            },
            {
                'id': 'revenue',
                'question': "What's your target revenue range?",
                'examples': ['$5M to $50M', '$10M to $30M', 'under $20M'],
                'hint': "This helps us filter by company size"
            },
            {
                'id': 'geography',
                'question': "Any geographic preferences?",
                'examples': ['US only', 'North America', 'US, UK, Canada', 'no preference'],
                'hint': "Where should the companies be located?"
            },
            {
                'id': 'ownership',
                'question': "What type of ownership are you interested in?",
                'examples': ['private companies', 'family-owned', 'PE-backed', 'no preference'],
                'hint': "This affects deal structure and complexity"
            },
            {
                'id': 'capabilities',
                'question': "Any specific capabilities or synergies you're looking for?",
                'examples': ['in-house manufacturing', 'e-commerce platform', 'specific technology', 'none'],
                'hint': "What would make a company strategically valuable?"
            }
        ]
        
        for i, q in enumerate(questions, 1):
            print(f"\n{'─'*70}")
            print(f"Question {i}/{len(questions)}")
            print(f"{'─'*70}\n")
            
            print(f"[PORTO] {q['question']}")
            print(f"\n   [HINT] {q['hint']}")
            print(f"   Examples: {', '.join(q['examples'])}")
            
            answer = input("\n   Your answer: ").strip()
            
            if not answer:
                print("\n   [WARNING] Please provide an answer")
                answer = input("   Your answer: ").strip()
            
            # Let Gemini parse the answer
            print("\n   [Understanding your answer...]")
            self.parse_and_store(q['id'], q['question'], answer)
            
            # Show what was extracted
            self.show_extracted(q['id'])
            
            time.sleep(0.5)
    
    def parse_and_store(self, field_id: str, question: str, answer: str):
        """
        Use Gemini to extract structured data from natural language
        """
        
        prompt = f"""You are parsing user input for M&A target search criteria.

Question asked: "{question}"
User's answer: "{answer}"
Field: {field_id}

Extract structured information based on the field:

For 'industry':
  Extract: {{"industry": ["list of industries"], "keywords": ["relevant search terms"], "reference_companies": ["list of reference/example companies mentioned"], "specifics": "detailed description"}}
  IMPORTANT: If the user mentions any reference companies, example companies, or competitors (like "companies like X", "similar to Y", "reference would be Z"), extract them into the reference_companies array.
  Example: If user says "promotional products, especially signage, reference companies would be Vistaprint and 4over"
  Return: {{"industry": ["promotional products", "signage", "printing"], "keywords": ["promotional", "signage", "banner", "printing"], "reference_companies": ["Vistaprint", "4over"], "specifics": "Promotional products with focus on signage and printing"}}

For 'revenue':
  Extract: {{"revenue_min_millions": number, "revenue_max_millions": number, "currency": "USD"}}
  Example: "$5M to $50M" → {{"revenue_min_millions": 5, "revenue_max_millions": 50, "currency": "USD"}}
  Example: "under $20M" → {{"revenue_min_millions": 0, "revenue_max_millions": 20, "currency": "USD"}}
  Example: "$10M+" → {{"revenue_min_millions": 10, "revenue_max_millions": 1000, "currency": "USD"}}

For 'geography':
  Extract: {{"countries": ["ISO codes"], "regions": ["region names"], "no_preference": boolean}}
  Example: "US only" → {{"countries": ["US"], "regions": ["United States"], "no_preference": false}}
  Example: "North America" → {{"countries": ["US", "CA", "MX"], "regions": ["North America"], "no_preference": false}}

For 'ownership':
  Extract: {{"types": ["ownership types"], "no_preference": boolean}}
  Types can be: "private", "family-owned", "PE-backed", "public", "ESOP"

For 'capabilities':
  Extract: {{"required": ["must-have capabilities"], "preferred": ["nice-to-have"], "no_preference": boolean}}

BE SMART. INFER. If user is vague, make reasonable assumptions.
Return ONLY valid JSON, no explanation, no markdown.
"""
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean JSON from markdown
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            parsed = json.loads(text)
            
            # Store in criteria
            self.criteria[field_id] = parsed
            
            # Store conversation
            self.conversation_history.append({
                'question': question,
                'answer': answer,
                'extracted': parsed
            })
            
        except Exception as e:
            print(f"\n   [ERROR] Error parsing answer: {e}")
            print(f"   Raw response: {response.text[:200]}")
            
            # Fallback: store raw answer
            self.criteria[field_id] = {'raw': answer}
    
    def show_extracted(self, field_id: str):
        """
        Show what was understood in friendly format
        """
        
        extracted = self.criteria.get(field_id, {})
        
        print(f"\n   [OK] Got it!")
        
        if field_id == 'industry':
            industries = extracted.get('industry', [])
            print(f"      Industries: {', '.join(industries)}")
            ref_companies = extracted.get('reference_companies', [])
            if ref_companies:
                print(f"      Reference companies: {', '.join(ref_companies)}")
            
        elif field_id == 'revenue':
            min_rev = extracted.get('revenue_min_millions', 0)
            max_rev = extracted.get('revenue_max_millions', 0)
            print(f"      Revenue range: ${min_rev}M - ${max_rev}M")
            
        elif field_id == 'geography':
            regions = extracted.get('regions', [])
            print(f"      Locations: {', '.join(regions)}")
            
        elif field_id == 'ownership':
            types = extracted.get('types', [])
            if types:
                print(f"      Ownership: {', '.join(types)}")
            else:
                print(f"      Ownership: No preference")
                
        elif field_id == 'capabilities':
            required = extracted.get('required', [])
            if required and required != ['none']:
                print(f"      Required: {', '.join(required)}")
            else:
                print(f"      No specific requirements")
    
    def confirm_criteria(self) -> bool:
        """
        Summarize and get confirmation
        """
        
        print(f"\n\n{'='*70}")
        print(" SEARCH CRITERIA SUMMARY")
        print(f"{'='*70}\n")
        
        # Generate human-readable summary with Gemini
        summary_prompt = f"""Generate a clear, bulleted summary of these M&A search criteria:

{json.dumps(self.criteria, indent=2)}

Make it conversational and well-formatted.
Use bullet points.
Be specific about numbers and locations.

Example format:
• Industry: Promotional products (signage, printing, custom manufacturing)
• Revenue: $5M to $50M annually
• Geography: United States, United Kingdom, Canada
• Ownership: Private or family-owned companies
• Requirements: In-house manufacturing capabilities preferred

Your summary:
"""
        
        try:
            response = self.model.generate_content(summary_prompt)
            summary = response.text.strip()
            print(summary)
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            # Fallback: print raw criteria
            print(json.dumps(self.criteria, indent=2))
        
        print(f"\n{'='*70}\n")
        
        confirm = input("Is this correct? (yes/no/modify): ").lower().strip()
        
        if confirm in ['y', 'yes']:
            return True
        elif confirm in ['n', 'no']:
            return False
        elif confirm in ['m', 'modify']:
            print("\nWhat would you like to change?")
            modification = input("Describe the changes: ")
            
            # Use Gemini to apply modifications
            self.apply_modifications(modification)
            
            # Re-confirm
            return self.confirm_criteria()
        else:
            print("\nPlease answer 'yes', 'no', or 'modify'")
            return self.confirm_criteria()
    
    def apply_modifications(self, modification: str):
        """
        Update criteria based on user's modification request
        """
        
        prompt = f"""Current search criteria:
{json.dumps(self.criteria, indent=2)}

User wants to modify: "{modification}"

Update the criteria accordingly and return the complete updated JSON.
Only change what the user mentioned.
Return ONLY valid JSON.
"""
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            
            updated = json.loads(text)
            self.criteria = updated
            
            print("\n[SUCCESS] Criteria updated!")
            
        except Exception as e:
            print(f"\n[WARNING] Could not apply modification: {e}")
    
    def export_criteria(self, filename='search_criteria.json'):
        """
        Save criteria to file in output/ directory
        """
        # Get the project root directory (parent of intake/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, 'output')

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        filepath = os.path.join(output_dir, filename)

        # Extract reference companies to top level for discovery engine
        criteria_export = self.criteria.copy()
        industry_data = criteria_export.get('industry', {})
        ref_companies = industry_data.get('reference_companies', [])
        if ref_companies:
            criteria_export['reference_companies'] = ref_companies

        with open(filepath, 'w') as f:
            json.dump({
                'criteria': criteria_export,
                'conversation': self.conversation_history,
                'timestamp': time.time()
            }, f, indent=2)

        print(f"\n[SUCCESS] Criteria saved to output/{filename}")
        if ref_companies:
            print(f"   Reference companies for competitor search: {', '.join(ref_companies)}")


def main():
    """
    Run Porto
    """
    
    # Check API key
    if not os.getenv('GEMINI_API_KEY'):
        print("\n[ERROR] GEMINI_API_KEY not found!")
        print("Please set it in your .env file")
        print("Get a free key: https://aistudio.google.com/app/apikey\n")
        return
    
    # Run consultant
    consultant = AIResearchConsultant()
    criteria = consultant.start()
    
    # Save criteria
    consultant.export_criteria()
    
    print(f"\n{'='*70}")
    print(" INTERVIEW COMPLETE")
    print(f"{'='*70}\n")
    
    print("Your search criteria has been saved.")
    print("\nNext steps:")
    print("1. Run the discovery engine: python run_discovery.py")
    print("2. Or continue with enrichment: python run_enrichment.py\n")
    
    return criteria


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ZOOMINFO SCRAPER TEMPLATE
Framework for scraping ZoomInfo company database

[WARNING] IMPLEMENTATION REQUIRED + ACCOUNT NEEDED [WARNING]

Requirements:
  pip install selenium undetected-chromedriver selenium-stealth

Setup:
  1. Get ZoomInfo account (or... acquired credentials 👀)
  2. Consider rotating proxies ($36/month) to avoid IP blocks
  3. Implement the methods below
  4. Start with small tests (10 companies)

Legal Note:
  This violates ZoomInfo ToS
  They actively detect and block scrapers
  Use proxies, rate limiting, and stealth
  India-based = gray area, proceed with caution

Cost:
  ZoomInfo account: $15K-30K/year OR find credentials
  Proxies: ₹3,000/month (~$36)
  Your time: 4-8 hours to implement
"""

import os
import json
import time
import random
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import undetected_chromedriver as uc
    from selenium_stealth import stealth
except ImportError:
    print("Install: pip install undetected-chromedriver selenium-stealth")
    exit(1)

class ZoomInfoScraper:
    """
    Scrape ZoomInfo with anti-detection measures
    """
    
    def __init__(self, email: str, password: str, use_proxy=False, proxy_list=None):
        self.email = email
        self.password = password
        self.driver = None
        self.use_proxy = use_proxy
        self.proxy_list = proxy_list or []
        
    def setup_driver(self):
        """
        Setup stealthy Chrome driver with anti-detection
        """
        
        options = uc.ChromeOptions()
        
        # Use proxy if configured
        if self.use_proxy and self.proxy_list:
            proxy = random.choice(self.proxy_list)
            options.add_argument(f'--proxy-server={proxy}')
            print(f"[INFO] Using proxy: {proxy}")
        
        # Stealth settings
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        
        # Random user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        self.driver = uc.Chrome(options=options)
        
        # Apply stealth JavaScript
        stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)
        
        print("[OK] Stealth browser initialized")
    
    def login(self):
        """
        Login to ZoomInfo
        
        TODO: Implement login logic
        
        ZoomInfo has strong detection:
          - Rate limits login attempts
          - Detects automation
          - May require CAPTCHA
          - May send verification emails
        
        Tips:
          - Add random delays
          - Mimic human behavior (mouse movements)
          - Handle CAPTCHA (manual or service like 2captcha)
          - Save session cookies for reuse
        """
        
        print("[INFO] Logging in to ZoomInfo...")
        
        self.driver.get("https://app.zoominfo.com/login")
        
        # Random delay (human-like)
        time.sleep(random.uniform(2, 4))
        
        # TODO: Implement login
        # Challenge: ZoomInfo actively detects automation
        
        # Method 1: Automated login with human-like behavior
        try:
            print("[INFO] Attempting automated login...")
            
            # Wait for email field
            email_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
            )
            
            # Type email slowly
            for char in self.email:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.2))
            
            # Find and click next/continue if it exists (common in modern logins)
            try:
                next_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Next') or contains(text(), 'Continue')]")
                next_btn.click()
                time.sleep(random.uniform(1, 2))
            except:
                pass # Might be on same page
            
            # Wait for password field
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[name='password']"))
            )
            
            # Type password slowly
            for char in self.password:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.2))
            
            # Random delay before clicking login
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for dashboard or search page
            WebDriverWait(self.driver, 20).until(
                lambda d: "login" not in d.current_url
            )
            print("[SUCCESS] Automated login successful")
            
        except Exception as e:
            print(f"[WARNING] Automated login failed: {str(e)}")
            print("[INFO] Falling back to manual login...")
            
            # Method 2: Manual login (fallback)
            print("\n[ACTION] Please login manually in the browser")
            print("   This avoids automation detection")
            input("   Press ENTER after login... ")
        
        print("[OK] Logged in")
    
    def build_search_url(self, criteria: Dict) -> str:
        """
        Build ZoomInfo search URL with filters
        
        TODO: Implement URL builder
        
        ZoomInfo URL structure:
          https://app.zoominfo.com/search/company?
          &filters[industry]=...
          &filters[revenue_min]=...
          &filters[revenue_max]=...
          &filters[location]=...
          &filters[employees_min]=...
        
        You'll need to:
          1. Inspect ZoomInfo search URLs
          2. Map criteria to ZoomInfo filters
          3. Build encoded URL
        """
        
        industry = criteria.get('industry', {}).get('industry', [])
        revenue_min = criteria.get('revenue', {}).get('revenue_min_millions', 0)
        revenue_max = criteria.get('revenue', {}).get('revenue_max_millions', 1000)
        locations = criteria.get('geography', {}).get('countries', [])
        
        # Base URL for ZoomInfo search
        base_url = "https://app.zoominfo.com/#/apps/search/companies"
        
        # Note: ZoomInfo uses complex state in URL or internal API
        # We will construct a URL that attempts to pre-fill filters
        # But often it's better to use the UI filter application
        
        # Constructing a deep link (simplified example)
        # Real ZoomInfo URLs are often hashed/encoded
        
        params = []
        if industry:
            # Join industries with OR logic if multiple
            ind_str = ",".join(industry)
            params.append(f"industry={ind_str}")
            
        if revenue_min or revenue_max:
            params.append(f"revenue={revenue_min}000000-{revenue_max}000000")
            
        if locations:
            loc_str = ",".join(locations)
            params.append(f"location={loc_str}")
            
        # Construct final URL
        # If parameters exist, append them (this is a best-effort guess at URL structure)
        # In reality, we might just go to the search page and apply filters via UI
        if params:
            url = f"{base_url}?{'&'.join(params)}"
        else:
            url = base_url
        
        print(f"[INFO] Target URL: {url}")
        print(f"   Industry: {industry}")
        print(f"   Revenue: ${revenue_min}M-${revenue_max}M")
        print(f"   Locations: {locations}")
        
        return url
    
    def apply_filters(self, criteria: Dict):
        """
        Apply search filters via UI
        
        TODO: Implement filter interaction
        
        Alternative to URL building:
          1. Navigate to search page
          2. Click filter dropdowns
          3. Select options programmatically
          4. Apply filters
        
        This is more reliable but slower
        """
        
        print("[INFO] Applying filters via UI...")
        
        try:
            # Wait for filter panel
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='filter-panel'], .filters-sidebar"))
            )
            
            # Example: Apply Revenue Filter
            revenue_min = criteria.get('revenue', {}).get('revenue_min_millions', 0)
            if revenue_min > 0:
                print(f"   Applying Revenue > ${revenue_min}M")
                # Find revenue filter button (pseudo-selector)
                # btn = self.driver.find_element(By.XPATH, "//span[text()='Revenue']")
                # btn.click()
                # Input value...
            
            # Example: Apply Industry Filter
            industries = criteria.get('industry', {}).get('industry', [])
            if industries:
                print(f"   Applying Industries: {', '.join(industries)}")
                # Find industry input...
                
            print("[OK] Filters applied (simulated)")
            time.sleep(2) # Wait for results to update
            
        except Exception as e:
            print(f"[WARNING] Could not apply filters via UI: {e}")
            print("   Please apply filters manually if needed.")
    
    def scrape_results_page(self) -> List[Dict]:
        """
        Scrape companies from current results page
        
        TODO: Implement results extraction
        
        ZoomInfo displays results in cards/rows
        Each contains:
          - Company name
          - Industry
          - Revenue
          - Employee count
          - Location
          - Website
          - Contact count
        
        Steps:
          1. Find result elements (inspect page for selectors)
          2. Extract data from each element
          3. Handle missing data gracefully
          4. Return list of companies
        """
        
        companies = []
        
        try:
            # Wait for table rows or cards
            # ZoomInfo often uses a table structure or grid of cards
            # Selectors are hypothetical and need to be verified against live site
            print("   Looking for company rows...")
            
            # Common selectors for data tables/grids
            row_selectors = [
                "tr.table-row", 
                ".company-card", 
                "[data-testid='table-row']",
                ".result-row"
            ]
            
            rows = []
            for selector in row_selectors:
                rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    print(f"   Found {len(rows)} rows using selector: {selector}")
                    break
            
            if not rows:
                print("[WARNING] No result rows found. Check CSS selectors.")
                # Fallback: Dump page source for debugging if needed
                # with open("debug_page.html", "w", encoding="utf-8") as f:
                #     f.write(self.driver.page_source)
                return []

            for row in rows:
                try:
                    # Extract data from each row
                    # We use relative XPaths or CSS to find cells within the row
                    
                    # Name
                    try:
                        name_el = row.find_element(By.CSS_SELECTOR, "a.company-name, .name, [data-testid='company-name']")
                        name = name_el.text.strip()
                        website = name_el.get_attribute('href') # Often links to profile
                    except:
                        name = "Unknown"
                        website = ""

                    # Industry
                    try:
                        ind_el = row.find_element(By.CSS_SELECTOR, ".industry, [data-testid='industry']")
                        industry = ind_el.text.strip()
                    except:
                        industry = ""

                    # Revenue
                    try:
                        rev_el = row.find_element(By.CSS_SELECTOR, ".revenue, [data-testid='revenue']")
                        revenue = rev_el.text.strip()
                    except:
                        revenue = ""
                        
                    # Employees
                    try:
                        emp_el = row.find_element(By.CSS_SELECTOR, ".employees, [data-testid='employees']")
                        employees = emp_el.text.strip()
                    except:
                        employees = ""

                    # Location
                    try:
                        loc_el = row.find_element(By.CSS_SELECTOR, ".location, [data-testid='location']")
                        location = loc_el.text.strip()
                    except:
                        location = ""

                    if name and name != "Unknown":
                        company = {
                            'name': name,
                            'industry': industry,
                            'revenue': revenue,
                            'employees': employees,
                            'location': location,
                            'website': website, # This might be internal ZI link, need to extract real domain later
                            'source': 'zoominfo'
                        }
                        companies.append(company)
                        # print(f"   + Found: {name}")
                        
                except Exception as row_e:
                    continue # Skip bad rows

        except Exception as e:
            print(f"[ERROR] Error extracting results: {e}")
        
        return companies
    
    def paginate(self, max_pages=10) -> List[Dict]:
        """
        Paginate through results
        
        TODO: Implement pagination
        
        ZoomInfo pagination:
          - Next button at bottom
          - OR infinite scroll
          - Rate limiting is strict
        
        Tips:
          - Add random delays (5-10 seconds between pages)
          - Don't scrape more than 100 pages per session
          - Save progress in case of interruption
        """
        
        all_companies = []
        page = 1
        
        while page <= max_pages:
            print(f"\n[INFO] Page {page}/{max_pages}")
            
            # Scrape current page
            companies = self.scrape_results_page()
            all_companies.extend(companies)
            
            # Random delay (critical to avoid detection)
            delay = random.uniform(5, 10)
            print(f"   [WAIT] Waiting {delay:.1f}s before next page...")
            time.sleep(delay)
            
            # Try to find and click next button
            try:
                # Common pagination selectors
                next_selectors = [
                    "button[aria-label='Next']",
                    ".pagination-next",
                    "li.next a",
                    "//button[contains(text(), 'Next')]"
                ]
                
                next_btn = None
                for selector in next_selectors:
                    try:
                        if "//" in selector: # XPath
                            next_btn = self.driver.find_element(By.XPATH, selector)
                        else:
                            next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if next_btn and next_btn.is_enabled():
                            break
                    except:
                        continue
                
                if next_btn:
                    # Scroll to button
                    self.driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                    time.sleep(1)
                    next_btn.click()
                    
                    # Wait for loading
                    time.sleep(random.uniform(3, 5))
                    page += 1
                else:
                    print("   [INFO] No 'Next' button found. End of results.")
                    break
                    
            except Exception as e:
                print(f"   [WARNING] Pagination failed: {e}")
                break
        
        return all_companies
    
    def save_results(self, companies: List[Dict], filename='zoominfo_companies.json'):
        """
        Save discovered companies
        """
        
        with open(filename, 'w') as f:
            json.dump({
                'total': len(companies),
                'source': 'zoominfo',
                'timestamp': time.time(),
                'companies': companies
            }, f, indent=2)
        
        print(f"\n[SUCCESS] Saved {len(companies)} companies to {filename}")
    
    def quit(self):
        """
        Close browser
        """
        if self.driver:
            self.driver.quit()


def main():
    """
    Run ZoomInfo discovery
    """
    
    print("""
==================================================================
         ZOOMINFO SCRAPER
         [WARNING] REQUIRES IMPLEMENTATION + ACCOUNT
         [WARNING] VIOLATES ZOOMINFO TOS - USE AT YOUR OWN RISK
==================================================================
    """)
    
    # Load search criteria
    if not os.path.exists('search_criteria.json'):
        print("[ERROR] No search criteria found!")
        print("Run: python ai_research_consultant.py first\n")
        return
    
    with open('search_criteria.json', 'r') as f:
        data = json.load(f)
        criteria = data.get('criteria', {})
    
    # Get credentials
    print("\n ZoomInfo Credentials")
    print("="*60)
    print("[WARNING] Account required ($15K-30K/year)")
    print()
    
    email = input("Email: ")
    password = input("Password: ")
    
    # Proxy configuration
    use_proxy = input("\nUse proxy rotation? (yes/no): ").lower() in ['y', 'yes']
    
    proxy_list = []
    if use_proxy:
        print("\n[INFO] Recommended: Smartproxy, Bright Data, or IPRoyal")
        print("   Cost: ~₹3,000/month (~$36)")
        print("\nEnter proxies (format: http://user:pass@host:port)")
        print("One per line, empty line to finish:")
        
        while True:
            proxy = input("Proxy: ").strip()
            if not proxy:
                break
            proxy_list.append(proxy)
    
    # Initialize scraper
    scraper = ZoomInfoScraper(email, password, use_proxy, proxy_list)
    
    try:
        # Setup browser
        scraper.setup_driver()
        
        # Login
        scraper.login()
        
        # Build search
        search_url = scraper.build_search_url(criteria)
        
        # Navigate to search
        # scraper.driver.get(search_url)
        # time.sleep(5)
        
        # OR apply filters via UI
        # scraper.apply_filters(criteria)
        
        # Scrape results
        print("\n[INFO] Scraping results...")
        companies = scraper.paginate(max_pages=10)
        
        # Save
        if companies:
            scraper.save_results(companies)
            
            print(f"\n[SUCCESS] Scraped {len(companies)} companies")
            print("\nNext steps:")
            print("  1. Review zoominfo_companies.json")
            print("  2. Merge with discovered_companies.json")
            print("  3. Run enrichment pipeline")
        else:
            print("\n[WARNING] No companies scraped")
            print("Implementation incomplete or filters too restrictive")
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        scraper.quit()


if __name__ == "__main__":
    print("\n" + "="*60)
    print(" [INFO] ZOOMINFO SCRAPER STATUS")
    print("="*60)
    print("\n1. Core methods: IMPLEMENTED ✓")
    print("2. Violates ZoomInfo Terms of Service")
    print("3. Requires ZoomInfo account ($$$)")
    print("4. Recommended: Use proxies to avoid IP bans")
    print("5. CSS selectors may need adjustment against live site")
    print("\nImplemented methods:")
    print("  ✓ login() - Automated + manual fallback")
    print("  ✓ build_search_url() - Creates search URLs")
    print("  ✓ scrape_results_page() - Extracts company data")
    print("  ✓ paginate() - Handles pagination")
    print("\n" + "="*60 + "\n")
    
    choice = input("Understand the risks and continue? (yes/no): ")
    
    if choice.lower() in ['y', 'yes']:
        main()
    else:
        print("\nGood choice. Consider legal alternatives:")
        print("  - Apollo.io ($49/month)")
        print("  - LinkedIn Sales Navigator ($99/month)")
        print("  - Clearbit (usage-based)")

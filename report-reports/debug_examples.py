#!/usr/bin/env python3
"""Debug: check example patterns in description of high-contrast patent"""
import sys, re
from playwright.sync_api import sync_playwright

pid = "US20250284151A1"
url = f"https://patents.google.com/patent/{pid}/en"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    )
    page = browser.new_page(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(4000)
    for i in range(8):
        page.evaluate("window.scrollBy(0, 2500)")
        page.wait_for_timeout(1000)
    
    body = page.inner_text('body')
    
    # Get description section
    desc_m = re.search(r'Description\s*\n([\s\S]{200,}?)\n\s*Claims\b', body, re.IGNORECASE)
    desc = desc_m.group(1) if desc_m else ''
    
    print(f"Description length: {len(desc)} chars")
    
    # Search for various example patterns
    patterns = [
        (r'Example\s+\d+', 'Example N'),
        (r'EXAMPLE\s+\d+', 'EXAMPLE N'),
        (r'Working\s+Example', 'Working Example'),
        (r'Comparative\s+Example', 'Comparative Example'),
        (r'Application\s+Example', 'Application Example'),
        (r'Blend\s+Example', 'Blend Example'),
        (r'Mixture\s+Example', 'Mixture Example'),
        (r'Table\s+\d+', 'Table N'),
        (r'Composition\s+\d+', 'Composition N'),
        (r'Formulation\s+\d+', 'Formulation N'),
        (r'Preparation\s+Example', 'Preparation Example'),
        (r'\[\d{4}\]', 'Patent paragraph [NNNN]'),
        (r'contrast\s+ratio', 'contrast ratio'),
        (r'high\s+contrast', 'high contrast'),
        (r'VHR', 'VHR'),
        (r'Δε\s*[=≈~]', 'delta-epsilon value'),
        (r'Δn\s*[=≈~]', 'delta-n value'),
        (r'clearing\s+point', 'clearing point'),
        (r'negative\s+dielectric', 'negative dielectric'),
        (r'positive\s+dielectric', 'positive dielectric'),
    ]
    
    for pat, label in patterns:
        matches = re.findall(pat, desc, re.IGNORECASE)
        print(f"  {label}: {len(matches)} matches")
        if matches and len(matches) <= 10:
            for m in matches[:5]:
                print(f"    - {m}")
    
    # Show text around "contrast" mentions
    print(f"\n--- Contrast context (first 5) ---")
    for m in re.finditer(r'.{0,80}contrast.{0,80}', desc, re.IGNORECASE):
        print(f"  ...{m.group().strip()}...")
        if m.start() > 50000:
            break
    
    # Show last 2000 chars of description (usually contains example tables)
    print(f"\n--- Last 3000 chars of description ---")
    print(desc[-3000:])
    
    browser.close()

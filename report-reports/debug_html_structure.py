#!/usr/bin/env python3
"""Debug: dump HTML structure of one patent to understand DOM layout"""
import sys, json, re
from playwright.sync_api import sync_playwright

pid = "US20250284151A1"  # Highest contrast count
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
    
    html = page.content()
    
    # Save full HTML for analysis
    with open('/data/.hermes/skills/research/patent-playwright-scraper/reports/debug_patent.html', 'w') as f:
        f.write(html)
    
    # Look for key structural elements
    print(f"HTML length: {len(html)}")
    
    # Check for common patterns
    patterns_to_check = [
        (r'itemprop="abstract"', 'abstract itemprop'),
        (r'class="abstract"', 'abstract class'),
        (r'itemprop="description"', 'description itemprop'),
        (r'class="description"', 'description class'),
        (r'itemprop="claims"', 'claims itemprop'),
        (r'class="claim-text"', 'claim-text class'),
        (r'class="claim"', 'claim class'),
        (r'num="1"', 'num=1 attribute'),
        (r'application-timeline', 'timeline'),
        (r'style-scope', 'style-scope (Polymer)'),
        (r'<section', 'section tags'),
        (r'<patent-text', 'patent-text tags'),
        (r'class="style-scope patent-result"', 'patent-result class'),
        (r'hidden="true"', 'hidden elements'),
    ]
    
    for pat, label in patterns_to_check:
        count = len(re.findall(pat, html))
        if count > 0:
            print(f"  {label}: {count} matches")
            # Show first occurrence context
            m = re.search(pat, html)
            if m:
                start = max(0, m.start() - 50)
                end = min(len(html), m.end() + 200)
                print(f"    Context: ...{html[start:end]}...")
    
    # Check for shadow DOM indicators
    print(f"\nShadow DOM / Polymer checks:")
    shadow_count = len(re.findall(r'shadow-root|shadowRoot|#shadow-root', html))
    print(f"  Shadow root mentions: {shadow_count}")
    
    # Look for patent-text elements (common in new GP)
    pt_count = len(re.findall(r'<patent-text', html))
    print(f"  patent-text elements: {pt_count}")
    
    # Try extracting abstract from inner_text
    body = page.inner_text('body')
    abs_m = re.search(r'Abstract\s*\n([\s\S]{30,2000}?)\n\s*(?:Classifications|Description|Images|DESCRI)', body, re.IGNORECASE)
    if abs_m:
        print(f"\nAbstract from inner_text: {abs_m.group(1).strip()[:200]}...")
    else:
        print(f"\nAbstract NOT found in inner_text")
        # Show what follows "Abstract" in body
        abs_pos = body.find('Abstract')
        if abs_pos >= 0:
            print(f"  After 'Abstract': {body[abs_pos:abs_pos+300]}")
    
    # Check description
    desc_m = re.search(r'Description\s*\n([\s\S]{200,}?)\n\s*Claims\b', body, re.IGNORECASE)
    if desc_m:
        desc_text = desc_m.group(1).strip()
        print(f"\nDescription from inner_text: {len(desc_text)} chars")
        print(f"  First 200: {desc_text[:200]}")
        # Check for examples
        ex_count = len(re.findall(r'(?:Example|EXAMPLE)\s*\d+', desc_text))
        print(f"  Example mentions: {ex_count}")
    else:
        print(f"\nDescription NOT found in inner_text")
        desc_pos = body.find('Description')
        if desc_pos >= 0:
            print(f"  After 'Description': {body[desc_pos:desc_pos+300]}")
    
    # Timeline dates
    try:
        events = page.evaluate("""() => {
            const els = document.querySelectorAll('.event.style-scope.application-timeline');
            return Array.from(els).map(e => e.textContent.trim().substring(0, 100));
        }""")
        print(f"\nTimeline events from JS: {len(events)}")
        for evt in events[:5]:
            print(f"  {evt}")
    except Exception as e:
        print(f"  Timeline JS error: {e}")
    
    browser.close()

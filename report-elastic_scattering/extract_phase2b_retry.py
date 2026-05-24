#!/usr/bin/env python3
"""
Phase 2b: Fix date extraction, retry timeouts, verify B2 dates
"""
import json, re, time, sys, os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))

# Patents that timed out or need date verification
RETRY_PIDS = [
    'US20230295510A1', 'US20230272282A1',  # timed out
    'US12305103B2', 'US12264276B2', 'US12163081B2', 'US12104109B2',  # timed out B2s
    'US12404452B2', 'US12325817B2', 'US11802243B2',  # need date check (neg DA)
    'US20240067879A1', 'US20240360362A1',  # re-extract with dates
]

def extract_with_dates(page, pid):
    """Extract patent with robust date extraction"""
    url = f"https://patents.google.com/patent/{pid}/en"
    print(f"  Extracting {pid}...")
    
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45000)
        # Wait for content but don't need full networkidle
        time.sleep(5)
        
        # Get full page text
        body_text = page.evaluate("() => document.body.innerText") or ""
        
        # Robust date extraction from page text
        dates = {}
        
        # Method 1: timeline items via JS
        js_dates = page.evaluate("""() => {
            const result = {};
            // Try timeline elements
            document.querySelectorAll('time, [datetime]').forEach(el => {
                const dt = el.getAttribute('datetime') || el.innerText;
                if (dt && dt.match(/\\d{4}-\\d{2}-\\d{2}/)) {
                    const text = el.closest('div, span, li, td')?.innerText || '';
                    if (text.match(/filed|filing/i)) result.filed = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                    if (text.match(/priority/i)) result.priority = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                    if (text.match(/publish|publication/i)) result.published = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                }
            });
            return result;
        }""") or {}
        dates.update(js_dates)
        
        # Method 2: regex on body text
        if not dates.get('filed'):
            m = re.search(r'(?:Filing|Filed)\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', body_text, re.I)
            if m: dates['filed'] = m.group(1)
        
        if not dates.get('priority'):
            # Priority date from "Priority" section or PCT table
            m = re.search(r'Priority\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', body_text, re.I)
            if m: dates['priority'] = m.group(1)
            else:
                # Look in the metadata table
                m = re.search(r'(\d{4}-\d{2}-\d{2})\s*.*?Priority', body_text[:5000], re.I)
                if m: dates['priority'] = m.group(1)
        
        if not dates.get('published'):
            m = re.search(r'Publication\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', body_text, re.I)
            if m: dates['published'] = m.group(1)
        
        # Method 3: Find all dates in the first 3000 chars and classify
        if not dates:
            all_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', body_text[:5000])
            if all_dates:
                # Usually first date is priority/filing
                dates['priority'] = all_dates[0]
                if len(all_dates) > 1:
                    dates['published'] = all_dates[-1]
        
        # Method 4: Derive from PID for US applications
        if pid.startswith('US') and pid.endswith('A1') and not dates.get('filed'):
            m = re.match(r'US(\d{4})', pid)
            if m:
                pub_year = int(m.group(1))
                dates['derived_pub_year'] = pub_year
                # Filing is typically 18 months before publication
                dates['estimated_filed_year'] = pub_year - 1
        
        # Get title
        title = page.evaluate("""() => {
            const el = document.querySelector('invention-title');
            return el ? el.innerText.trim() : '';
        }""") or ""
        if not title:
            m = re.search(r'(.+?)\s*-\s*Google Patents', body_text[:200])
            if m: title = m.group(1).strip()
        
        # Get abstract
        abstract = page.evaluate("""() => {
            const el = document.querySelector('div.abstract');
            return el ? el.innerText.trim() : '';
        }""") or ""
        
        # Get claim 1
        claim1 = page.evaluate("""() => {
            const claims = document.querySelectorAll('div.claim, li.claim');
            if (claims.length > 0) return claims[0].innerText.trim();
            const ep_claims = document.querySelectorAll('ol.claims li.claim');
            if (ep_claims.length > 0) return ep_claims[0].innerText.trim();
            return '';
        }""") or ""
        
        # Count neg/pos DA
        text_lower = body_text[:80000].lower()
        neg_patterns = [
            r'negative\s+dielectric\s+anisotropy',
            r'Δε\s*<\s*0',
            r'dielectric\s+anisotropy\s+Δε\s+is\s+negative',
            r'Δε\s+is\s+negative',
            r'negative\s+Δε',
        ]
        pos_patterns = [
            r'positive\s+dielectric\s+anisotropy',
            r'Δε\s*>\s*0',
            r'Δε\s+is\s+positive',
            r'positive\s+Δε',
        ]
        neg_count = sum(len(re.findall(p, text_lower)) for p in neg_patterns)
        pos_count = sum(len(re.findall(p, text_lower)) for p in pos_patterns)
        
        # Elastic constants
        elastic_patterns = [
            r'elastic\s+constant', r'\bK11\b', r'\bK22\b', r'\bK33\b',
            r'splay\s+elastic', r'twist\s+elastic', r'bend\s+elastic',
        ]
        elastic_count = sum(len(re.findall(p, text_lower)) for p in elastic_patterns)
        
        # Scattering
        scatter_patterns = [r'scattering', r'light\s+scattering', r'forward\s+scattering']
        scatter_count = sum(len(re.findall(p, text_lower)) for p in scatter_patterns)
        
        is_negative_da = neg_count > pos_count and neg_count >= 2
        
        # Check date range
        filed_date = dates.get('filed', dates.get('priority', ''))
        if not filed_date and dates.get('estimated_filed_year'):
            filed_year = dates['estimated_filed_year']
            in_range = 2020 <= filed_year <= 2026
        elif filed_date:
            try:
                filed_year = int(filed_date[:4])
                in_range = 2020 <= filed_year <= 2026
            except:
                in_range = False
        else:
            in_range = False
        
        result = {
            'patent_id': pid,
            'title': title[:200],
            'abstract': abstract[:2000],
            'claim1': claim1[:2000],
            'dates': dates,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_da': is_negative_da,
            'elastic_count': elastic_count,
            'has_elastic': elastic_count > 0,
            'scatter_count': scatter_count,
            'has_scattering': scatter_count > 0,
            'in_date_range': in_range,
            'body_length': len(body_text),
        }
        
        print(f"    dates={dates}, neg={neg_count}, pos={pos_count}, "
              f"elastic={elastic_count}, scatter={scatter_count}, "
              f"negDA={is_negative_da}, inRange={in_range}")
        
        return result
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return {'patent_id': pid, 'error': str(e)}

def main():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        )
        page = ctx.new_page()
        
        for i, pid in enumerate(RETRY_PIDS):
            print(f"\n[{i+1}/{len(RETRY_PIDS)}] {pid}")
            result = extract_with_dates(page, pid)
            results.append(result)
            time.sleep(3)
        
        browser.close()
    
    # Save
    out_path = f"{BASE}/extract_phase2b_retry.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n\n========================================")
    print("PHASE 2b EXTRACTION SUMMARY")
    print("========================================")
    
    for r in results:
        pid = r['patent_id']
        if 'error' in r:
            print(f"  {pid}: ERROR - {r['error'][:80]}")
            continue
        
        dates = r.get('dates', {})
        filed = dates.get('filed', dates.get('priority', ''))
        neg = r.get('neg_da_count', 0)
        pos = r.get('pos_da_count', 0)
        is_neg = r.get('is_negative_da', False)
        in_range = r.get('in_date_range', False)
        elastic = r.get('has_elastic', False)
        scatter = r.get('has_scattering', False)
        
        marker = " *** NEG DA IN RANGE ***" if (is_neg and in_range) else (" (neg DA but out of range)" if is_neg else "")
        print(f"  {pid}: filed={filed}, neg={neg}, pos={pos}, elastic={elastic}, scatter={scatter}, inRange={in_range}{marker}")
    
    new_neg = [r for r in results if r.get('is_negative_da') and r.get('in_date_range')]
    print(f"\nNew confirmed neg DA in range: {len(new_neg)}")
    for r in new_neg:
        print(f"  {r['patent_id']}: filed={r['dates']}")

if __name__ == '__main__':
    main()

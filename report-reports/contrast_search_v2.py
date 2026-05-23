#!/usr/bin/env python3
"""Merck LC patent search - contrast focused, streamlined"""
import sys, json, re, time
sys.stdout.reconfigure(line_buffering=True)

from playwright.sync_api import sync_playwright

def search_one(assignee, query, cpc=""):
    url = f'https://patents.google.com/?assignee="{assignee}"&q={query}'
    if cpc:
        url += f"&cpc={cpc}"
    url += "&after=priority:20240101"
    
    print(f"Search: assignee={assignee} q={query} cpc={cpc}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(4000)
            for i in range(5):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1200)
            
            body = page.inner_text('body')
            
            # Extract patent IDs
            us_pats = set(re.findall(r'US\d{7,}[A-Z]\d?', body))
            wo_pats = set(re.findall(r'WO\d{4}/\d{4,6}', body))
            ep_pats = set(re.findall(r'EP\d{6,7}', body))
            all_pats = us_pats | wo_pats | ep_pats
            
            # Extract dates from DOM
            try:
                dates_data = page.evaluate('''() => {
                    const items = document.querySelectorAll('search-result-item, article');
                    return Array.from(items).map(item => {
                        const text = item.textContent;
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const published = text.match(/Published\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const pid = text.match(/((?:US|WO|EP)\\d+[A-Z]?\\d?)/);
                        return { patent_id: pid?.[1], filed: filed?.[1], published: published?.[1] };
                    }).filter(d => d.patent_id);
                }''')
            except:
                dates_data = []
            
            print(f"  Found: {len(all_pats)} patents, {len(dates_data)} with dates")
            return list(all_pats), dates_data
            
        except Exception as e:
            print(f"  Error: {e}")
            return [], []
        finally:
            browser.close()

def main():
    all_ids = set()
    date_map = {}
    
    # Round 1: Core searches with Merck Patent GmbH (most common assignee)
    searches = [
        ("Merck Patent GmbH", '"liquid crystal"+"contrast"', ""),
        ("Merck Patent GmbH", '"liquid crystal"+"high contrast"', ""),
        ("Merck Patent GmbH", '"liquid crystal"+"contrast ratio"', ""),
        ("Merck Patent GmbH", '"liquid crystal"+"negative dielectric anisotropy"+"contrast"', ""),
        ("Merck Patent GmbH", '"liquid crystal"'+''"contrast"'+''"VA"', ""),
        ("Merck KGaA", '"liquid crystal"+"contrast"', ""),
        ("Merck KGaA", '"liquid crystal"+"high contrast"', ""),
        ("Merck Electronics KGaA", '"liquid crystal"+"contrast"', ""),
        ("Merck Patent GmbH", '"liquid crystal"', "C09K19%2F30"),
    ]
    
    for assignee, query, cpc in searches:
        try:
            pids, ddata = search_one(assignee, query, cpc)
            all_ids.update(pids)
            for dd in ddata:
                pid = dd.get('patent_id', '')
                if pid:
                    date_map[pid] = {
                        'filing_date': dd.get('filed', ''),
                        'publication_date': dd.get('published', '')
                    }
        except Exception as e:
            print(f"  Failed: {e}")
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"TOTAL UNIQUE: {len(all_ids)}")
    
    us_ids = sorted([p for p in all_ids if p.startswith('US')])
    other_ids = sorted([p for p in all_ids if not p.startswith('US')])
    sorted_ids = us_ids + other_ids
    
    print(f"US: {len(us_ids)}, Other: {len(other_ids)}")
    
    for pid in sorted_ids:
        dm = date_map.get(pid, {})
        print(f"  {pid}  filed={dm.get('filing_date','?')}  pub={dm.get('publication_date','?')}")
    
    output = {
        'total_unique': len(all_ids),
        'patent_ids': sorted_ids,
        'date_map': date_map,
        'us_count': len(us_ids),
        'other_count': len(other_ids)
    }
    
    out_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_search_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {out_path}")

if __name__ == '__main__':
    main()

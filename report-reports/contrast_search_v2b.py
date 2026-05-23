#!/usr/bin/env python3
"""Merck LC patent search - contrast focused, expanded round 2"""
import sys, json, re, time
sys.stdout.reconfigure(line_buffering=True)

from playwright.sync_api import sync_playwright

def search_one(assignee, query, cpc=""):
    url = f'https://patents.google.com/?assignee="{assignee}"&q={query}'
    if cpc:
        url += f"&cpc={cpc}"
    url += "&after=priority:20230101"
    
    print(f"Search: {assignee} | q={query} | cpc={cpc}")
    
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
            for i in range(8):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1200)
            
            body = page.inner_text('body')
            
            us_pats = set(re.findall(r'US\d{7,}[A-Z]\d?', body))
            wo_pats = set(re.findall(r'WO\d{4}/\d{4,6}', body))
            ep_pats = set(re.findall(r'EP\d{6,7}', body))
            all_pats = us_pats | wo_pats | ep_pats
            
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
    # Load existing results
    existing_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_search_results.json'
    with open(existing_path) as f:
        existing = json.load(f)
    
    all_ids = set(existing['patent_ids'])
    date_map = dict(existing.get('date_map', {}))
    print(f"Existing: {len(all_ids)} patents")
    
    # Expanded searches - broader keywords, wider date range (from 2023)
    searches = [
        # Broader: just "contrast" with Merck Patent GmbH (most prolific)
        ("Merck Patent GmbH", '"liquid crystal" contrast', ""),
        # Broader: LC medium + contrast (no quotes on contrast)
        ("Merck Patent GmbH", '"liquid crystal medium" contrast', ""),
        # VA mode + contrast (VA mode uses neg dielectric LC)
        ("Merck Patent GmbH", '"liquid crystal" "VA" contrast', ""),
        # PSVA + contrast (Polymer Stabilized VA)
        ("Merck Patent GmbH", '"liquid crystal" "PSVA" contrast', ""),
        # IPS/FFS mode + contrast
        ("Merck Patent GmbH", '"liquid crystal" "IPS" contrast', ""),
        # Negative dielectric + contrast (no "liquid crystal" requirement)
        ("Merck Patent GmbH", '"negative dielectric anisotropy" contrast', ""),
        # LC display + contrast
        ("Merck Patent GmbH", '"liquid crystal display" contrast', ""),
        # Broader assignee coverage
        ("Merck Electronics KGaA", '"liquid crystal" contrast', ""),
        ("Merck Electronics KGaA", '"liquid crystal" "VA"', ""),
        ("Merck Electronics Ltd", '"liquid crystal" contrast', ""),
        # Without assignee restriction, but with CPC + Merck keyword
        ("Merck", '"liquid crystal" contrast', "C09K19%2F30"),
        # LC composition + display properties
        ("Merck Patent GmbH", '"liquid crystal medium" "display"', "C09K19%2F04"),
    ]
    
    for assignee, query, cpc in searches:
        try:
            pids, ddata = search_one(assignee, query, cpc)
            new_count = 0
            for pid in pids:
                if pid not in all_ids:
                    all_ids.add(pid)
                    new_count += 1
            for dd in ddata:
                pid = dd.get('patent_id', '')
                if pid:
                    if pid not in date_map:
                        date_map[pid] = {
                            'filing_date': dd.get('filed', ''),
                            'publication_date': dd.get('published', '')
                        }
            print(f"  New this round: {new_count}")
        except Exception as e:
            print(f"  Failed: {e}")
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"TOTAL UNIQUE: {len(all_ids)}")
    
    us_ids = sorted([p for p in all_ids if p.startswith('US')])
    wo_ids = sorted([p for p in all_ids if p.startswith('WO')])
    ep_ids = sorted([p for p in all_ids if p.startswith('EP')])
    sorted_ids = us_ids + wo_ids + ep_ids
    
    print(f"US: {len(us_ids)}, WO: {len(wo_ids)}, EP: {len(ep_ids)}")
    
    for pid in sorted_ids:
        dm = date_map.get(pid, {})
        print(f"  {pid}  filed={dm.get('filing_date','?')}  pub={dm.get('publication_date','?')}")
    
    output = {
        'total_unique': len(all_ids),
        'patent_ids': sorted_ids,
        'date_map': date_map,
        'us_count': len(us_ids),
        'wo_count': len(wo_ids),
        'ep_count': len(ep_ids)
    }
    
    out_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_search_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {out_path}")

if __name__ == '__main__':
    main()

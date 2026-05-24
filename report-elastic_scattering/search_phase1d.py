#!/usr/bin/env python3
"""Phase 1d: Alternative search strategy using URL-based patent discovery.
Google Patents inner_text fails to extract PIDs from search results,
so we use a different approach: extract from the page source / href links.
"""
import json, os, re, time
from urllib.parse import quote

REPORTS_DIR = '/data/.hermes/skills/research/patent-playwright-scraper/reports/elastic_scattering'

search_configs = [
    # Focus on finding more neg DA LC patents
    {"id": "Z1", "assignee": "Merck Patent GmbH", "q": '"negative dielectric anisotropy" liquid crystal', "label": "broad_neg_da_lc"},
    {"id": "Z2", "assignee": "Merck Electronics KGaA", "q": '"negative dielectric anisotropy" liquid crystal', "label": "elec_broad_neg_da_lc"},
    {"id": "Z3", "assignee": "Merck Patent GmbH", "q": 'negative dielectric anisotropy liquid crystal medium', "label": "no_quotes_neg_da"},
    {"id": "Z4", "assignee": "Merck Electronics KGaA", "q": 'negative dielectric anisotropy liquid crystal medium', "label": "elec_no_quotes"},
    {"id": "Z5", "assignee": "Merck Patent GmbH", "q": '"liquid-crystalline medium" "negative dielectric"', "label": "LCM_neg_da"},
    {"id": "Z6", "assignee": "Merck Patent GmbH", "q": '"liquid crystal" "negative Δε"', "label": "LC_neg_delta"},
    {"id": "Z7", "assignee": "Merck Patent GmbH", "q": '"VA mode" OR "IPS mode" "liquid crystal medium"', "label": "VA_IPS_LC_med"},
]

def build_url(cfg):
    base = "https://patents.google.com/?"
    params = [f'assignee={quote(cfg["assignee"])}']
    params.append(f'q={quote(cfg["q"])}')
    params.append("after=priority:20230101")
    return base + "&".join(params)

def search_google_patents_hrefs(url, scrolls=10):
    """Extract patent IDs from href links in the page source, not just inner_text"""
    from playwright.sync_api import sync_playwright
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            
            # More scrolls for complete loading
            for i in range(scrolls):
                page.evaluate("window.scrollBy(0, 3000)")
                page.wait_for_timeout(2500)
            
            # METHOD 1: Extract from href links (most reliable)
            href_data = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href]');
                const patents = [];
                links.forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const match = href.match(/\\/patent\\/(US\\d+|EP\\d+|WO\\d+\\/\\d+)/i);
                    if (match) patents.push(match[1]);
                });
                return [...new Set(patents)];
            }""")
            
            # METHOD 2: inner_text
            body = page.inner_text('body')
            us_pids = re.findall(r'\b(US\d{7,}[A-Z]?\d?)\b', body)
            ep_pids = re.findall(r'\b(EP\d{7,}[A-Z]?\d?)\b', body)
            wo_pids = re.findall(r'\b(WO\d{4}/\d+)\b', body)
            text_pids = list(set(us_pids + ep_pids + wo_pids))
            
            # Combine both methods
            all_pids = list(set(href_data + text_pids))
            
            # METHOD 3: Get search result items with more detail
            search_items = page.evaluate("""() => {
                const results = [];
                // Try multiple selectors for search result items
                const selectors = ['search-result-item', 'article', '.search-result', '[data-result]'];
                for (const sel of selectors) {
                    const items = document.querySelectorAll(sel);
                    items.forEach(item => {
                        const text = item.textContent || '';
                        const links = item.querySelectorAll('a[href*="/patent/"]');
                        const pids = [];
                        links.forEach(a => {
                            const m = a.getAttribute('href')?.match(/\\/patent\\/(US\\d+|EP\\d+|WO\\d+\\/\\d+)/i);
                            if (m) pids.push(m[1]);
                        });
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        if (pids.length > 0 || filed) {
                            results.push({pids: pids, filed: filed?.[1] || ''});
                        }
                    });
                    if (results.length > 0) break;
                }
                return results;
            }""")
            
            # Also get filing dates from timeline approach
            date_info = []
            try:
                date_data = page.evaluate("""() => {
                    const items = document.querySelectorAll('search-result-item, article, .search-result');
                    return Array.from(items).map(item => {
                        const text = item.textContent;
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const pid_matches = text.match(/(US\\d{5,}[A-Z]?\\d?|EP\\d{5,}[A-Z]?\\d?)/g);
                        return {patent_ids: pid_matches || [], filed: filed?.[1] || ''};
                    }).filter(d => d.patent_ids.length > 0 || d.filed);
                }""")
                date_info = date_data if date_data else []
            except: pass
            
            count_m = re.search(r'([\d,]+)\s+results?', body)
            
            results = {
                'href_pids': href_data,
                'text_pids': text_pids,
                'all_pids': all_pids,
                'search_items': search_items[:20],
                'date_info': date_info[:20],
                'results_count': int(count_m.group(1).replace(',','')) if count_m else 0,
            }
        except Exception as e:
            results = {'error': str(e), 'href_pids': [], 'text_pids': [], 'all_pids': [], 'search_items': [], 'date_info': []}
        finally:
            browser.close()
    return results

# Known neg DA patents
known_neg = {'US20250101305A1', 'US20250189829A1', 'US20250215323A1', 'US20250284151A1', 'EP4680691A1', 'EP4400561A1'}
known_all = {'US20250101305A1', 'US20250189829A1', 'US20250215323A1', 'US20250284151A1', 'EP4680691A1', 'EP4400561A1',
             'US12612551B2', 'US20250207032A1', 'US20250136868A1', 'US20250197723A1', 'US20250361444A1', 
             'EP4553132A1', 'EP4685208A1', 'US20250085595A1'}

all_new = {}
all_new_dates = {}

for cfg in search_configs:
    url = build_url(cfg)
    print(f"\n[{cfg['id']}] {cfg['label']}", flush=True)
    print(f"  URL: {url[:120]}...", flush=True)
    result = search_google_patents_hrefs(url, scrolls=10)
    
    err = result.get('error')
    if err:
        print(f"  ERROR: {err}", flush=True)
        continue
    
    href_pids = result.get('href_pids', [])
    text_pids = result.get('text_pids', [])
    all_pids = result.get('all_pids', [])
    count = result.get('results_count', 0)
    
    print(f"  Total results: {count}, href_pids: {len(href_pids)}, text_pids: {len(text_pids)}, combined: {len(all_pids)}", flush=True)
    
    if href_pids:
        print(f"  HREF PIDs: {href_pids[:15]}", flush=True)
    if text_pids and text_pids != href_pids:
        print(f"  TEXT PIDs (extra): {list(set(text_pids) - set(href_pids))[:10]}", flush=True)
    
    # Search items with dates
    for item in result.get('search_items', [])[:5]:
        print(f"  Item: pids={item.get('pids',[])}, filed={item.get('filed','')}", flush=True)
    
    # Track new ones
    for pid in all_pids:
        if pid not in known_all:
            if pid not in all_new:
                all_new[pid] = []
            all_new[pid].append(cfg['id'])
    
    for item in result.get('date_info', []):
        for pid in item.get('patent_ids', []):
            if pid and pid not in all_new_dates and item.get('filed'):
                all_new_dates[pid] = item['filed']
    
    time.sleep(3)

print(f"\n{'='*80}")
print("HREF-BASED SEARCH - NEW PATENTS")
print(f"{'='*80}")
print(f"New unique PIDs: {len(all_new)}")
for pid in sorted(all_new.keys()):
    src = all_new.get(pid, [])
    filed = all_new_dates.get(pid, '?')
    print(f"  {pid}: filed={filed}, found_by={src}")

# Save
with open(os.path.join(REPORTS_DIR, 'search_phase1d_hrefs.json'), 'w') as f:
    json.dump({'all_new': all_new, 'all_new_dates': all_new_dates}, f, ensure_ascii=False, indent=2, default=str)

print(f"\nDone. Need to extract & validate these new patents for negative DA + elastic/scattering")

#!/usr/bin/env python3
"""Merck elastic constant / low scattering LC patent search - Phase 1"""
import json, os, re, time, sys
from urllib.parse import quote

REPORTS_DIR = '/data/.hermes/skills/research/patent-playwright-scraper/reports/elastic_scattering'
os.makedirs(REPORTS_DIR, exist_ok=True)

# Search URL configurations
search_configs = [
    # === Elastic Constant Direction ===
    {"id": "E1", "assignee": "Merck Patent GmbH", "q": '"elastic constant" "liquid crystal"', "label": "elastic_constant"},
    {"id": "E2", "assignee": "Merck Patent GmbH", "q": '"elastic" "negative dielectric"', "label": "elastic_neg_diel"},
    {"id": "E3", "assignee": "Merck Patent GmbH", "q": '"K33" "liquid crystal"', "label": "K33_LC"},
    {"id": "E4", "assignee": "Merck Patent GmbH", "q": '"K11" "liquid crystal"', "label": "K11_LC"},
    {"id": "E5", "assignee": "Merck KGaA", "q": '"elastic constant" "liquid crystal"', "label": "KGaA_elastic"},
    {"id": "E6", "assignee": "Merck Electronics KGaA", "q": '"elastic" "liquid crystal"', "label": "Electronics_elastic"},
    {"id": "E7", "assignee": "Merck Performance Materials Germany GmbH", "q": '"elastic" "liquid crystal"', "label": "PerfMat_elastic"},
    # === Scattering Direction ===
    {"id": "S1", "assignee": "Merck Patent GmbH", "q": '"scattering" "liquid crystal"', "label": "scattering_LC"},
    {"id": "S2", "assignee": "Merck Patent GmbH", "q": '"low scattering" "liquid crystal"', "label": "low_scatter_LC"},
    {"id": "S3", "assignee": "Merck Patent GmbH", "q": '"scattering" "negative dielectric"', "label": "scatter_neg_diel"},
    {"id": "S4", "assignee": "Merck Patent GmbH", "q": '"light scattering" "liquid crystal"', "label": "light_scatter_LC"},
    {"id": "S5", "assignee": "Merck KGaA", "q": '"scattering" "liquid crystal"', "label": "KGaA_scattering"},
    {"id": "S6", "assignee": "Merck Electronics KGaA", "q": '"scattering" "liquid crystal"', "label": "Electronics_scatter"},
    # === CPC + keyword combos ===
    {"id": "C1", "assignee": "Merck Patent GmbH", "q": '"elastic"', "cpc": "C09K19/30", "label": "CPC_elastic"},
    {"id": "C2", "assignee": "Merck Patent GmbH", "q": '"scattering"', "cpc": "C09K19/30", "label": "CPC_scatter"},
    {"id": "C3", "assignee": "Merck Patent GmbH", "q": '"elastic constant"', "cpc": "C09K19/04", "label": "CPC_elastic_comp"},
]

def build_url(cfg):
    base = "https://patents.google.com/?"
    params = [f'assignee={quote(cfg["assignee"])}']
    params.append(f'q={quote(cfg["q"])}')
    if "cpc" in cfg:
        params.append(f'cpc={quote(cfg["cpc"])}')
    params.append("after=priority:20230101")
    return base + "&".join(params)

def search_google_patents(url, scrolls=6):
    """Search Google Patents, scroll, extract patent IDs and dates from results page."""
    from playwright.sync_api import sync_playwright
    
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            
            # Scroll to load more results
            for i in range(scrolls):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1500)
            
            # Extract body text
            body = page.inner_text('body')
            
            # Extract patent IDs from body text
            us_patents = re.findall(r'\b(US\d{7,}[A-Z]?\d?)\b', body)
            ep_patents = re.findall(r'\b(EP\d{7,}[A-Z]?\d?)\b', body)
            wo_patents = re.findall(r'\b(WO\d{4}/\d+)\b', body)
            
            all_patents = list(set(us_patents + ep_patents + wo_patents))
            
            # Try to extract dates from search results DOM
            date_info = []
            try:
                date_data = page.evaluate('''() => {
                    const items = document.querySelectorAll('search-result-item, article');
                    return Array.from(items).map(item => {
                        const text = item.textContent;
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const published = text.match(/Published\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const pid = text.match(/(US\\d{5,}[A-Z]?\\d?|EP\\d{5,}[A-Z]?\\d?)/);
                        return { 
                            patent_id: pid?.[1] || '',
                            filed: filed?.[1] || '', 
                            published: published?.[1] || ''
                        };
                    }).filter(d => d.patent_id);
                }''')
                date_info = date_data if date_data else []
            except:
                pass
            
            # Count results indicator
            results_count = 0
            count_m = re.search(r'([\d,]+)\s+results?', body)
            if count_m:
                results_count = int(count_m.group(1).replace(',', ''))
            
            results = {
                'patent_ids': all_patents,
                'date_info': date_info,
                'results_count': results_count,
                'body_length': len(body),
                'body_preview': body[:500]
            }
            
        except Exception as e:
            results = {'error': str(e), 'patent_ids': [], 'date_info': []}
        finally:
            browser.close()
    
    return results

# Run all searches
all_found = {}
all_date_info = {}

for cfg in search_configs:
    url = build_url(cfg)
    print(f"\n[{cfg['id']}] {cfg['label']}: {url[:120]}...", flush=True)
    
    result = search_google_patents(url, scrolls=6)
    
    pids = result.get('patent_ids', [])
    dates = result.get('date_info', [])
    count = result.get('results_count', 0)
    err = result.get('error', None)
    
    if err:
        print(f"  ERROR: {err}", flush=True)
        continue
    
    print(f"  Results count: {count}, Patent IDs found: {len(pids)}", flush=True)
    print(f"  IDs: {pids[:15]}", flush=True)
    if dates:
        for d in dates[:5]:
            print(f"    {d['patent_id']}: filed={d['filed']}, pub={d['published']}", flush=True)
    
    # Track which search found each patent
    for pid in pids:
        if pid not in all_found:
            all_found[pid] = []
        all_found[pid].append(cfg['id'])
    
    for d in dates:
        pid = d.get('patent_id', '')
        if pid and pid not in all_date_info:
            all_date_info[pid] = d
    
    # Save intermediate
    with open(os.path.join(REPORTS_DIR, f'search_{cfg["id"]}.json'), 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    time.sleep(2)  # polite delay

# Summary
print("\n" + "="*80)
print("SEARCH SUMMARY")
print("="*80)
print(f"Total unique patent IDs: {len(all_found)}")

# Categorize
us_ids = [p for p in all_found if p.startswith('US')]
ep_ids = [p for p in all_found if p.startswith('EP')]
wo_ids = [p for p in all_found if p.startswith('WO')]
print(f"US patents: {len(us_ids)}")
print(f"EP patents: {len(ep_ids)}")
print(f"WO patents: {len(wo_ids)}")

# Filter by date 2024-2026 (from date_info)
recent_pids = []
for pid, d in all_date_info.items():
    filed = d.get('filed', '')
    if filed and filed[:4] in ('2024', '2025', '2026'):
        recent_pids.append(pid)

# Also add patents without date info (we'll filter in extraction phase)
all_pid_list = list(all_found.keys())

print(f"\nPatents with filing date 2024-2026 (from search page): {len(recent_pids)}")
for pid in recent_pids:
    d = all_date_info.get(pid, {})
    searches = all_found.get(pid, [])
    print(f"  {pid}: filed={d.get('filed','?')}, pub={d.get('published','?')}, found_by={searches}")

# Save combined results
combined = {
    'all_found': all_found,
    'all_date_info': all_date_info,
    'recent_pids': recent_pids,
    'all_pid_list': all_pid_list,
    'stats': {
        'total_unique': len(all_found),
        'us_count': len(us_ids),
        'ep_count': len(ep_ids),
        'wo_count': len(wo_ids),
        'recent_count': len(recent_pids)
    }
}
with open(os.path.join(REPORTS_DIR, 'search_combined.json'), 'w') as f:
    json.dump(combined, f, ensure_ascii=False, indent=2, default=str)

print(f"\nResults saved to {REPORTS_DIR}/search_combined.json")
print(f"Total unique patent IDs for next phase: {len(all_pid_list)}")

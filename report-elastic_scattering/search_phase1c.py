#!/usr/bin/env python3
"""Phase 1c: Broad search for Merck negative DA LC patents 2024-2026,
then filter for elastic/scattering content"""
import json, os, re, time
from urllib.parse import quote

REPORTS_DIR = '/data/.hermes/skills/research/patent-playwright-scraper/reports/elastic_scattering'

# Already found neg DA patents
existing_neg = {'US20250101305A1', 'US20250189829A1', 'US20250215323A1', 'US20250284151A1', 'EP4680691A1', 'EP4400561A1'}

# Broader searches targeting negative DA LC from Merck
search_configs = [
    # Broader neg DA searches with various assignees
    {"id": "Y1", "assignee": "Merck Patent GmbH", "q": '"negative dielectric anisotropy" "liquid crystal" "medium"', "label": "broad_neg_DA_medium"},
    {"id": "Y2", "assignee": "Merck Electronics KGaA", "q": '"negative dielectric anisotropy" "liquid crystal" "medium"', "label": "Elec_broad_neg_DA"},
    {"id": "Y3", "assignee": "Merck KGaA", "q": '"negative dielectric anisotropy" "liquid crystal" "medium"', "label": "KGaA_broad_neg_DA"},
    {"id": "Y4", "assignee": "Merck Patent GmbH", "q": '"negative dielectric" "liquid-crystal" "medium"', "label": "hyphen_neg_DA"},
    {"id": "Y5", "assignee": "Merck Patent GmbH", "q": '"negative Δε" "medium"', "label": "delta_eps_medium"},
    {"id": "Y6", "assignee": "Merck Patent GmbH", "q": '"vertical alignment" "negative dielectric" "liquid crystal"', "label": "VA_neg_DA"},
    {"id": "Y7", "assignee": "Merck Electronics KGaA", "q": '"vertical alignment" "liquid crystal medium"', "label": "Elec_VA_medium"},
    {"id": "Y8", "assignee": "Merck Patent GmbH", "q": '"liquid crystal medium" "elastic" OR "scattering"', "label": "LC_med_elastic_OR_scatter"},
]

def build_url(cfg):
    base = "https://patents.google.com/?"
    params = [f'assignee={quote(cfg["assignee"])}']
    params.append(f'q={quote(cfg["q"])}')
    params.append("after=priority:20230101")
    return base + "&".join(params)

def search_google_patents(url, scrolls=8):
    from playwright.sync_api import sync_playwright
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            for i in range(scrolls):
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(2000)
            body = page.inner_text('body')
            us_patents = re.findall(r'\b(US\d{7,}[A-Z]?\d?)\b', body)
            ep_patents = re.findall(r'\b(EP\d{7,}[A-Z]?\d?)\b', body)
            wo_patents = re.findall(r'\b(WO\d{4}/\d+)\b', body)
            all_pids = list(set(us_patents + ep_patents + wo_patents))
            date_info = []
            try:
                date_data = page.evaluate("""() => {
                    const items = document.querySelectorAll('search-result-item, article');
                    return Array.from(items).map(item => {
                        const text = item.textContent;
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const pid = text.match(/(US\\d{5,}[A-Z]?\\d?|EP\\d{5,}[A-Z]?\\d?)/);
                        return { patent_id: pid?.[1] || '', filed: filed?.[1] || '' };
                    }).filter(d => d.patent_id);
                }""")
                date_info = date_data if date_data else []
            except: pass
            count_m = re.search(r'([\d,]+)\s+results?', body)
            results = {
                'patent_ids': all_pids,
                'date_info': date_info,
                'results_count': int(count_m.group(1).replace(',','')) if count_m else 0,
            }
        except Exception as e:
            results = {'error': str(e), 'patent_ids': [], 'date_info': []}
        finally:
            browser.close()
    return results

# Load existing results
with open(os.path.join(REPORTS_DIR, 'search_combined.json'), 'r') as f:
    existing = json.load(f)
existing_all = set(existing.get('all_pid_list', []))

new_pids = {}
new_date_info = {}

for cfg in search_configs:
    url = build_url(cfg)
    print(f"\n[{cfg['id']}] {cfg['label']}: {url[:120]}...", flush=True)
    result = search_google_patents(url, scrolls=8)
    pids = result.get('patent_ids', [])
    dates = result.get('date_info', [])
    count = result.get('results_count', 0)
    err = result.get('error', None)
    
    if err:
        print(f"  ERROR: {err}", flush=True)
        continue
    
    print(f"  Results: {count}, PIDs: {len(pids)} -> {pids[:15]}", flush=True)
    for d in dates[:8]:
        print(f"    {d['patent_id']}: filed={d['filed']}", flush=True)
    
    for pid in pids:
        if pid not in existing_all and pid not in existing_neg:
            if pid not in new_pids:
                new_pids[pid] = []
            new_pids[pid].append(cfg['id'])
    
    for d in dates:
        pid = d.get('patent_id', '')
        if pid and pid not in new_date_info:
            new_date_info[pid] = d
    
    time.sleep(2)

# Filter for truly new patents
truly_new = {pid: src for pid, src in new_pids.items() if pid not in existing_all}

print(f"\n{'='*80}")
print("BROAD SEARCH - NEW PATENTS (not in previous searches)")
print(f"{'='*80}")
print(f"New unique PIDs: {len(truly_new)}")

# Also show ALL neg DA patents found (including already-known)
all_neg_candidates = {}
for cfg in search_configs:
    url = build_url(cfg)
    result = search_google_patents.__wrapped__ if hasattr(search_google_patents, '__wrapped__') else None
    # Can't re-call, use saved results

# Just list the new ones with dates
for pid in sorted(truly_new.keys()):
    d = new_date_info.get(pid, {})
    filed = d.get('filed', '?')
    src = truly_new.get(pid, [])
    print(f"  {pid}: filed={filed}, found_by={src}")

# Save
with open(os.path.join(REPORTS_DIR, 'search_phase1c_broad.json'), 'w') as f:
    json.dump({
        'truly_new': truly_new, 
        'new_date_info': new_date_info,
        'all_new_pids': new_pids
    }, f, ensure_ascii=False, indent=2, default=str)

print(f"\nNeed to extract these {len(truly_new)} new patents and check for negative DA + elastic/scattering")

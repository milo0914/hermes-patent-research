#!/usr/bin/env python3
"""Additional search - Phase 1b: strict negative DA + elastic/scattering"""
import json, os, re, time, sys
from urllib.parse import quote

REPORTS_DIR = '/data/.hermes/skills/research/patent-playwright-scraper/reports/elastic_scattering'

search_configs = [{'id': 'X1', 'assignee': 'Merck Patent GmbH', 'q': '"negative dielectric anisotropy" "elastic" "liquid crystal"', 'label': 'neg_DA_elastic_LC'}, {'id': 'X2', 'assignee': 'Merck Patent GmbH', 'q': '"negative dielectric anisotropy" "scattering" "liquid crystal"', 'label': 'neg_DA_scatter_LC'}, {'id': 'X3', 'assignee': 'Merck KGaA', 'q': '"negative dielectric anisotropy" "elastic" "liquid crystal"', 'label': 'KGaA_neg_DA_elastic'}, {'id': 'X4', 'assignee': 'Merck Electronics KGaA', 'q': '"negative dielectric anisotropy" "liquid crystal"', 'label': 'Elec_neg_DA_LC'}, {'id': 'X5', 'assignee': 'Merck Patent GmbH', 'q': '"negative Δε" "liquid crystal"', 'label': 'neg_delta_eps_LC'}, {'id': 'X6', 'assignee': 'Merck Patent GmbH', 'q': '"negative dielectric" "K33" "liquid crystal"', 'label': 'neg_DA_K33'}, {'id': 'X7', 'assignee': 'Merck Patent GmbH', 'q': '"negative dielectric" "K11" "liquid crystal"', 'label': 'neg_DA_K11'}, {'id': 'X8', 'assignee': 'Merck Patent GmbH', 'q': '"elastic constant" "negative dielectric"', 'label': 'elastic_neg_DA'}, {'id': 'X9', 'assignee': 'Merck Electronics KGaA', 'q': '"negative dielectric anisotropy" "elastic constant"', 'label': 'Elec_neg_DA_elastic'}, {'id': 'X10', 'assignee': 'Merck Patent GmbH', 'q': '"negative dielectric anisotropy" "K1" "liquid crystal"', 'label': 'neg_DA_K1'}]

def build_url(cfg):
    base = "https://patents.google.com/?"
    params = [f'assignee={quote(cfg["assignee"])}']
    params.append(f'q={quote(cfg["q"])}')
    params.append("after=priority:20230101")
    return base + "&".join(params)

def search_google_patents(url, scrolls=6):
    from playwright.sync_api import sync_playwright
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            for i in range(scrolls):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1500)
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
            except:
                pass
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

new_pids = {}  # pid -> [search_ids]
new_date_info = {}

for cfg in search_configs:
    url = build_url(cfg)
    print(f"\n[{cfg['id']}] {cfg['label']}: {url[:120]}...", flush=True)
    result = search_google_patents(url, scrolls=6)
    pids = result.get('patent_ids', [])
    dates = result.get('date_info', [])
    count = result.get('results_count', 0)
    print(f"  Results: {count}, Patent IDs: {len(pids)} -> {pids[:10]}", flush=True)
    for d in dates[:5]:
        print(f"    {d['patent_id']}: filed={d['filed']}", flush=True)
    for pid in pids:
        if pid not in new_pids:
            new_pids[pid] = []
        new_pids[pid].append(cfg['id'])
    for d in dates:
        pid = d.get('patent_id', '')
        if pid and pid not in new_date_info:
            new_date_info[pid] = d
    time.sleep(2)

# Filter out already-extracted patents
already = set(existing.get('all_pid_list', []))
truly_new = {pid: src for pid, src in new_pids.items() if pid not in already}

print(f"\n{'='*80}")
print(f"ADDITIONAL SEARCH RESULTS")
print(f"{'='*80}")
print(f"New unique PIDs: {len(truly_new)}")
for pid, src in sorted(truly_new.items()):
    d = new_date_info.get(pid, {})
    filed = d.get('filed', '?')
    print(f"  {pid}: filed={filed}, found_by={src}")

# Save
with open(os.path.join(REPORTS_DIR, 'search_phase2_additional.json'), 'w') as f:
    json.dump({'new_pids': new_pids, 'new_date_info': new_date_info, 'truly_new': truly_new}, f, ensure_ascii=False, indent=2, default=str)

print(f"\nSaved to search_phase2_additional.json")

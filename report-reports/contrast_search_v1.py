#!/usr/bin/env python3
"""Merck LC patent search - contrast focused, 2024-2026"""
import sys, json, re, time
sys.stdout.reconfigure(line_buffering=True)

from playwright.sync_api import sync_playwright

ASSIGNEES = [
    "Merck Patent GmbH",
    "Merck KGaA",
    "Merck Performance Materials Germany GmbH",
    "EMD Chemicals Inc",
    "Merck Performance Materials Ltd",
    "EMD Performance Materials Corp",
    "Merck Electronics KGaA",
    "Merck Electronics Ltd",
]

SEARCH_QUERIES = [
    '"liquid crystal"+"contrast"',
    '"liquid crystal medium"+"negative dielectric anisotropy"+"contrast"',
    '"liquid crystal"+"high contrast"',
    '"liquid crystal"+"contrast ratio"',
]

CPC_CODES = ["C09K19/30", "C09K19/04", "G02F1/1337"]

def build_search_urls():
    urls = []
    for assignee in ASSIGNEES[:3]:
        for q in SEARCH_QUERIES:
            url = f'https://patents.google.com/?assignee="{assignee}"&q={q}&after=priority:20240101'
            urls.append(("assignee_kw", assignee, q, url))

    for cpc in CPC_CODES[:2]:
        for q in SEARCH_QUERIES[:2]:
            url = f'https://patents.google.com/?q={q}+assignee:"Merck"&cpc={cpc.replace("/","%2F")}&after=priority:20240101'
            urls.append(("cpc_kw", cpc, q, url))

    for assignee in ASSIGNEES[3:6]:
        for q in SEARCH_QUERIES[:2]:
            url = f'https://patents.google.com/?assignee="{assignee}"&q={q}&after=priority:20240101'
            urls.append(("assignee_kw_ext", assignee, q, url))

    return urls

def search_google_patents(url_tuple):
    category, param1, param2, url = url_tuple
    print(f"  Searching: [{category}] {param1} | {param2}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)

            for i in range(6):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1500)

            body = page.inner_text('body')

            us_patents = re.findall(r'US\d{7,}[A-Z]\d?', body)
            wo_patents = re.findall(r'WO\d{4}/\d{4,6}', body)
            ep_patents = re.findall(r'EP\d{6,7}', body)

            all_patents = us_patents + wo_patents + ep_patents
            seen = set()
            unique = []
            for pid in all_patents:
                if pid not in seen:
                    seen.add(pid)
                    unique.append(pid)

            try:
                dates_data = page.evaluate('''() => {
                    const items = document.querySelectorAll('search-result-item, article');
                    return Array.from(items).map(item => {
                        const text = item.textContent;
                        const filed = text.match(/Filed\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const published = text.match(/Published\\s+(\\d{4}-\\d{2}-\\d{2})/);
                        const pid = text.match(/((?:US|WO|EP)\\d+[A-Z]?\\d?)/);
                        return {
                            patent_id: pid?.[1],
                            filed: filed?.[1],
                            published: published?.[1]
                        };
                    }).filter(d => d.patent_id);
                }''')
            except:
                dates_data = []

            results = {
                'category': category,
                'param1': param1,
                'param2': param2,
                'patent_ids': unique[:30],
                'dates_data': dates_data[:30],
                'total_found': len(unique),
                'url': url
            }
            print(f"    Found {len(unique)} patents (US:{len(us_patents)}, WO:{len(wo_patents)}, EP:{len(ep_patents)})")

        except Exception as e:
            print(f"    Error: {e}")
            results = {'category': category, 'param1': param1, 'param2': param2,
                       'patent_ids': [], 'dates_data': [], 'total_found': 0, 'url': url, 'error': str(e)}
        finally:
            browser.close()

    return results

def main():
    urls = build_search_urls()
    print(f"Total search URLs: {len(urls)}")
    print("=" * 60)

    all_patent_ids = {}
    all_dates_data = []

    for i, url_tuple in enumerate(urls):
        print(f"\n[{i+1}/{len(urls)}]")
        result = search_google_patents(url_tuple)

        for pid in result.get('patent_ids', []):
            if pid not in all_patent_ids:
                all_patent_ids[pid] = {
                    'source': result['category'],
                    'assignee': result['param1'],
                    'query': result['param2'],
                }

        for dd in result.get('dates_data', []):
            if dd.get('patent_id'):
                all_dates_data.append(dd)

    print("\n" + "=" * 60)
    print(f"TOTAL UNIQUE PATENTS: {len(all_patent_ids)}")

    date_map = {}
    for dd in all_dates_data:
        pid = dd.get('patent_id', '')
        if pid and (dd.get('filed') or dd.get('published')):
            date_map[pid] = {
                'filing_date': dd.get('filed', ''),
                'publication_date': dd.get('published', ''),
            }

    us_ids = sorted([p for p in all_patent_ids if p.startswith('US')])
    other_ids = sorted([p for p in all_patent_ids if not p.startswith('US')])
    sorted_ids = us_ids + other_ids

    output = {
        'total_unique': len(all_patent_ids),
        'patent_ids': sorted_ids,
        'patent_meta': {pid: all_patent_ids[pid] for pid in sorted_ids},
        'date_map': date_map,
        'us_count': len(us_ids),
        'other_count': len(other_ids)
    }

    out_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_search_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"US patents: {len(us_ids)}")
    print(f"Other patents: {len(other_ids)}")
    print(f"Date map entries: {len(date_map)}")
    print(f"Results saved to: {out_path}")

    for pid in sorted_ids[:40]:
        meta = all_patent_ids[pid]
        dm = date_map.get(pid, {})
        fd = dm.get('filing_date', 'N/A')
        print(f"  {pid}  filed={fd}  src={meta['source']}")

if __name__ == '__main__':
    main()

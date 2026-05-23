#!/usr/bin/env python3
"""
Merck 高對比 LCD 負介電液晶專利搜索 v2 — 精簡高效版
只跑最有效的 8 組搜索，每組滾動次數減少
"""

import re, json, time, os
from playwright.sync_api import sync_playwright

REPORTS_DIR = os.path.dirname(os.path.abspath(__file__))
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

def search_gp(url, label):
    """搜索 Google Patents"""
    ids, date_map, snippets = [], {}, {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        try:
            page = browser.new_page()
            page.set_extra_http_headers({'User-Agent': USER_AGENT})
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(4000)
            # 6 scrolls
            for _ in range(6):
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(1000)
            text = page.inner_text('body')
            # Extract patent IDs
            for pat in [r'(US\d{7,}[A-Z]\d?)', r'(WO\d{4}/\d+)', r'(EP\d{7,}[A-Z]\d?)']:
                ids.extend(re.findall(pat, text))
            # Extract dates from text
            for pid in set(ids):
                # Find context around patent ID
                idx = text.find(pid)
                if idx >= 0:
                    ctx = text[max(0,idx-50):idx+200]
                    dates_in_ctx = re.findall(r'(\d{4}-\d{2}-\d{2})', ctx)
                    if dates_in_ctx:
                        date_map[pid] = {'filing_date': dates_in_ctx[0] if len(dates_in_ctx)>0 else None}
                    snippets[pid] = ctx[:120].replace('\n',' ')
            page.close()
        except Exception as e:
            print(f"  ERROR [{label}]: {e}")
        finally:
            browser.close()
    # Deduplicate preserving order
    seen, unique = set(), []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            unique.append(pid)
    return unique, date_map, snippets

def main():
    urls = [
        ('S1: MPG+contrast+LC', 'https://patents.google.com/?assignee="Merck+Patent+GmbH"&q="contrast"+"liquid+crystal"&after=priority:20230101&sort=newest&num=100'),
        ('S2: MEK+contrast+LC', 'https://patents.google.com/?assignee="Merck+Electronics+KGaA"&q="contrast"+"liquid+crystal"&after=priority:20230101&sort=newest&num=100'),
        ('S3: MPG+high_contrast', 'https://patents.google.com/?assignee="Merck+Patent+GmbH"&q="high+contrast"+"liquid+crystal"&after=priority:20230101&sort=newest&num=100'),
        ('S4: MPG+contrast+negDA', 'https://patents.google.com/?assignee="Merck+Patent+GmbH"&q=contrast+"negative+dielectric"&after=priority:20230101&sort=newest&num=100'),
        ('S5: MPG+contrast+C09K19', 'https://patents.google.com/?assignee="Merck+Patent+GmbH"&q=contrast&cpc=C09K19/30&after=priority:20230101&sort=newest&num=100'),
        ('S6: MPG+contrast+VA', 'https://patents.google.com/?assignee="Merck+Patent+GmbH"&q=contrast+("VA+mode"+OR+"vertical+alignment")+"liquid+crystal"&after=priority:20230101&sort=newest&num=100'),
        ('S7: MKG+contrast+LC', 'https://patents.google.com/?assignee="Merck+KGaA"&q="contrast"+"liquid+crystal"&after=priority:20230101&sort=newest&num=100'),
        ('S8: MEK+contrast+C09K19', 'https://patents.google.com/?assignee="Merck+Electronics+KGaA"&q=contrast&cpc=C09K19/30&after=priority:20230101&sort=newest&num=100'),
    ]
    
    all_ids, seen, all_dm, all_sn = [], set(), {}, {}
    stats = []
    
    for label, url in urls:
        print(f"搜索 [{label}]...")
        ids, dm, sn = search_gp(url, label)
        new = [p for p in ids if p not in seen]
        seen.update(ids)
        all_ids.extend(new)
        all_dm.update(dm)
        all_sn.update(sn)
        print(f"  {len(ids)} 個 (新增 {len(new)})")
        stats.append({'label': label, 'total': len(ids), 'new': len(new)})
        time.sleep(1.5)
    
    # Merge with previously known contrast patents
    # From previous search (contrast_search_results.json), add any that weren't found
    prev_file = os.path.join(REPORTS_DIR, 'contrast_search_results.json')
    prev_ids = []
    if os.path.exists(prev_file):
        with open(prev_file) as f:
            prev = json.load(f)
        prev_ids = prev.get('patent_ids', [])
        for pid in prev_ids:
            if pid not in seen:
                all_ids.append(pid)
                seen.add(pid)
                print(f"  + 從舊搜索補充: {pid}")
    
    output = {
        'total_unique': len(all_ids),
        'patent_ids': all_ids,
        'date_map': all_dm,
        'snippets': all_sn,
        'search_stats': stats,
        'prev_search_ids': prev_ids,
    }
    
    out_path = os.path.join(REPORTS_DIR, 'contrast_focused_v2.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"搜索完成: {len(all_ids)} 個不重複專利")
    for s in stats:
        print(f"  {s['label']}: total={s['total']}, new={s['new']}")
    print(f"\n候選專利列表:")
    for i, pid in enumerate(all_ids, 1):
        fd = all_dm.get(pid, {}).get('filing_date', 'N/A')
        snip = all_sn.get(pid, '')[:60]
        print(f"  {i}. {pid} | FD:{fd} | {snip}")
    print(f"\n結果已保存: {out_path}")
    return output

if __name__ == '__main__':
    main()

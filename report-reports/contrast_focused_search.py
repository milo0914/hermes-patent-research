#!/usr/bin/env python3
"""
Merck KGaA 高對比 LCD 負介電液晶專利搜索 — Contrast 專注版
搜索策略：assignee + "contrast" + liquid crystal + 負介電相關
目標：filing date 2024-2026，至少 10 篇
"""

import re, json, time, os, sys
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

ASSIGNEE_ALIASES = [
    "Merck Patent GmbH",
    "Merck KGaA",
    "Merck Electronics KGaA",
    "Merck Performance Materials Germany GmbH",
    "EMD Performance Materials Corp",
    "Merck Display Materials Shanghai Co Ltd",
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

JS_EXTRACT_SEARCH_RESULTS = """
() => {
  const results = [];
  const items = document.querySelectorAll('search-result-item, .search-result-item, [class*="result-item"]');
  for (const item of items) {
    const text = item.innerText || '';
    const pnMatch = text.match(/(US\\d{7,}[A-Z]\\d?|WO\\d{4}\\/\\d+|EP\\d{7,}[A-Z]\\d?)/);
    if (!pnMatch) continue;
    const patentId = pnMatch[1];
    const dates = {};
    const allDates = text.match(/\\d{4}-\\d{2}-\\d{2}/g) || [];
    if (allDates.length >= 1) dates.priority_date = allDates[0];
    if (allDates.length >= 2) dates.filing_date = allDates[1];
    if (allDates.length >= 3) dates.publication_date = allDates[2];
    const filedMatch = text.match(/Filed[:\\s]+(\\d{4}-\\d{2}-\\d{2})/i);
    if (filedMatch) dates.filing_date = filedMatch[1];
    const titleSnippet = text.substring(0, 200).replace(/\\n/g, ' ');
    results.push({patent_id: patentId, dates: dates, snippet: titleSnippet});
  }
  return results;
}
"""

def build_contrast_search_urls():
    """構建 contrast 專注搜索 URL"""
    rounds = []
    
    # S1: assignee + "contrast" + "liquid crystal"
    for alias in ASSIGNEE_ALIASES[:4]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q="contrast"+"liquid+crystal"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S1: {alias} + contrast+LC', 'round': 1})
    
    # S2: assignee + "high contrast" + "liquid crystal"
    for alias in ASSIGNEE_ALIASES[:4]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q="high+contrast"+"liquid+crystal"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S2: {alias} + high_contrast+LC', 'round': 2})
    
    # S3: assignee + "contrast ratio" + "liquid crystal"
    for alias in ASSIGNEE_ALIASES[:4]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q="contrast+ratio"+"liquid+crystal"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S3: {alias} + contrast_ratio+LC', 'round': 3})
    
    # S4: assignee + contrast + "negative dielectric"
    for alias in ASSIGNEE_ALIASES[:4]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q=contrast+"negative+dielectric"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S4: {alias} + contrast+negDA', 'round': 4})
    
    # S5: assignee + contrast + CPC C09K19
    for alias in ASSIGNEE_ALIASES[:4]:
        for cpc in ['C09K19/30', 'C09K19/04']:
            url = (f'https://patents.google.com/?assignee="{alias}"'
                   f'&q=contrast'
                   f'&cpc={cpc}'
                   f'&after=priority:20230101'
                   f'&sort=newest&num=100')
            rounds.append({'url': url, 'label': f'S5: {alias} + contrast+{cpc}', 'round': 5})
    
    # S6: assignee + "contrast" + VA/PSVA mode
    for alias in ASSIGNEE_ALIASES[:3]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q=contrast+("VA+mode"+OR+"PSVA"+OR+"vertical+alignment")+liquid+crystal'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S6: {alias} + contrast+VA/PSVA', 'round': 6})
    
    # S7: assignee 別名 5-6 + contrast + LC
    for alias in ASSIGNEE_ALIASES[4:]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q=contrast+"liquid+crystal"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S7: {alias} + contrast+LC', 'round': 7})
    
    # S8: 寬鬆 — assignee + contrast + display (不只 LC)
    for alias in ASSIGNEE_ALIASES[:2]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q="contrast"+"display"+"liquid+crystal"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S8: {alias} + contrast+display+LC', 'round': 8})
    
    # S9: CPC C09K19 + contrast + negative (不限 assignee 但限定負介電CPC)
    url = (f'https://patents.google.com/?cpc=C09K19/30'
           f'&q=contrast+"liquid+crystal"+negative'
           f'&after=priority:20230101'
           f'&sort=newest&num=100')
    rounds.append({'url': url, 'label': f'S9: CPC C09K19/30 + contrast+LC+negative', 'round': 9})
    
    # S10: assignee + "contrast" + "LCD"
    for alias in ASSIGNEE_ALIASES[:3]:
        url = (f'https://patents.google.com/?assignee="{alias}"'
               f'&q="contrast"+"LCD"'
               f'&after=priority:20230101'
               f'&sort=newest&num=100')
        rounds.append({'url': url, 'label': f'S10: {alias} + contrast+LCD', 'round': 10})
    
    return rounds


def search_google_patents(search_url, label):
    """搜索 Google Patents 提取專利號列表"""
    patent_ids = []
    date_map = {}
    snippets = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        try:
            page = browser.new_page()
            page.set_extra_http_headers({'User-Agent': USER_AGENT})
            page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            
            # Scroll 8+ times to trigger dynamic loading
            for scroll in range(10):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1200)
            
            # JS extract search results
            try:
                js_results = page.evaluate(JS_EXTRACT_SEARCH_RESULTS)
                if js_results:
                    for item in js_results:
                        pid = item.get('patent_id', '')
                        if pid:
                            date_map[pid] = item.get('dates', {})
                            snippets[pid] = item.get('snippet', '')
            except Exception as e:
                print(f"  JS DOM 提取失敗: {e}")
            
            # Fallback: extract from page text
            text = page.inner_text('body')
            patterns = [
                r'(US\d{7,}[A-Z]\d?)',
                r'(WO\d{4}/\d+)',
                r'(EP\d{7,}[A-Z]\d?)',
            ]
            for pat in patterns:
                matches = re.findall(pat, text)
                patent_ids.extend(matches)
            
            page.close()
        except Exception as e:
            print(f"  搜索失敗 [{label}]: {e}")
        finally:
            browser.close()
    
    # Deduplicate
    seen = set()
    unique = []
    for pid in patent_ids:
        if pid not in seen:
            seen.add(pid)
            unique.append(pid)
    
    return unique, date_map, snippets


def main():
    print("=" * 90)
    print("Merck KGaA 高對比 LCD 負介電液晶專利搜索 — Contrast 專注版")
    print("=" * 90)
    
    search_rounds = build_contrast_search_urls()
    print(f"\n共 {len(search_rounds)} 組搜索 URL\n")
    
    all_patent_ids = []
    seen_ids = set()
    all_date_map = {}
    all_snippets = {}
    search_stats = []
    
    for sr in search_rounds:
        print(f"搜索 [{sr['label']}] (第 {sr['round']} 輪)")
        try:
            ids, dm, snips = search_google_patents(sr['url'], sr['label'])
            all_date_map.update(dm)
            all_snippets.update(snips)
            new_ids = [pid for pid in ids if pid not in seen_ids]
            seen_ids.update(ids)
            all_patent_ids.extend(new_ids)
            print(f"  獲得 {len(ids)} 個專利號（新增 {len(new_ids)}）；DOM日期 {len(dm)} 筆")
            search_stats.append({
                'label': sr['label'], 'round': sr['round'],
                'total': len(ids), 'new': len(new_ids), 'dom_dates': len(dm)
            })
        except Exception as e:
            print(f"  搜索異常: {e}")
            search_stats.append({
                'label': sr['label'], 'round': sr['round'],
                'total': 0, 'new': 0, 'dom_dates': 0, 'error': str(e)
            })
        time.sleep(2)
    
    # Also search the full-text page of already-known contrast patents from previous search
    # We need to check if the previously found 16 patents contain contrast keywords in their full text
    print(f"\n搜索總計: {len(all_patent_ids)} 個不重複專利號；日期映射 {len(all_date_map)} 筆")
    
    # Save results
    output = {
        'total_unique': len(all_patent_ids),
        'patent_ids': all_patent_ids,
        'date_map': all_date_map,
        'snippets': all_snippets,
        'search_stats': search_stats,
    }
    
    output_path = os.path.join(REPORTS_DIR, 'contrast_focused_search_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n搜索結果已保存: {output_path}")
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"搜索統計:")
    for s in search_stats:
        err = f" (ERROR: {s.get('error','')[:40]})" if s.get('error') else ''
        print(f"  {s['label']}: total={s['total']}, new={s['new']}{err}")
    print(f"\n總計不重複專利: {len(all_patent_ids)}")
    
    # Show all patent IDs with dates
    print(f"\n所有候選專利:")
    for i, pid in enumerate(all_patent_ids, 1):
        dates = all_date_map.get(pid, {})
        fd = dates.get('filing_date', 'N/A')
        snip = all_snippets.get(pid, '')[:80]
        print(f"  {i}. {pid} | FD:{fd} | {snip}")
    
    return output


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Merck 高對比 LCD 負介電液晶專利深度提取 v2
基於 inner_text 策略，提取：
- 標題、摘要、日期、申請人
- Claim 1 完整內容
- 負介電相關段落 (Δε, negative dielectric)
- contrast 相關段落 (contrast ratio, high contrast, contrast improvement)
- 混合實施例組成 + 物理參數
- 分子結構代碼
"""

import re, json, time, os, sys
from playwright.sync_api import sync_playwright

REPORTS_DIR = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

def extract_patent_deep(patent_id):
    """深度提取單篇專利"""
    url = f'https://patents.google.com/patent/{patent_id}/en'
    result = {'patent_id': patent_id, 'url': url, 'success': False}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        try:
            page = browser.new_page()
            page.set_extra_http_headers({'User-Agent': UA})
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)
            
            # Scroll to load full content
            for _ in range(8):
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(800)
            # Scroll back to top for metadata
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            
            text = page.inner_text('body')
            html = page.content()
            
            # === 1. 標題 ===
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ''
            # Clean: "US20250284151A1 - Liquid-crystal medium - Google Patents"
            title_clean = re.sub(r'^[A-Z]{2}\d+[A-Z]?\d?\s*[-–]\s*', '', title)
            title_clean = re.sub(r'\s*[-–]\s*Google Patents\s*$', '', title_clean)
            result['title'] = title_clean
            
            # === 2. 日期 (JS evaluate) ===
            try:
                js_dates = page.evaluate("""
                () => {
                    const dates = {};
                    const events = document.querySelectorAll('.event.style-scope.application-timeline');
                    let allText = '';
                    for (const el of events) { allText += el.innerText + '\\n'; }
                    const bodyText = document.body.innerText;
                    // Filing date
                    const fm = bodyText.match(/Filing\\s+date\\s+(\\d{4}-\\d{2}-\\d{2})/i);
                    if (fm) dates.filing_date = fm[1];
                    const pm = bodyText.match(/Priority\\s+date\\s+(\\d{4}-\\d{2}-\\d{2})/i);
                    if (pm) dates.priority_date = pm[1];
                    const pm2 = bodyText.match(/Publication\\s+date\\s+(\\d{4}-\\d{2}-\\d{2})/i);
                    if (pm2) dates.publication_date = pm2[1];
                    const gm = bodyText.match(/Grant\\s+date\\s+(\\d{4}-\\d{2}-\\d{2})/i);
                    if (gm) dates.grant_date = gm[1];
                    // Timeline events
                    const dp = /(\\d{4}-\\d{2}-\\d{2})\\s+(.+)/g;
                    let m;
                    while ((m = dp.exec(allText)) !== null) {
                        const evt = m[2].toLowerCase();
                        if ((evt.includes('filed') || evt.includes('filing')) && !dates.filing_date) dates.filing_date = m[1];
                        if (evt.includes('publication') && !dates.publication_date) dates.publication_date = m[1];
                        if ((evt.includes('granted') || evt.includes('grant')) && !dates.grant_date) dates.grant_date = m[1];
                        if (evt.includes('priority') && !dates.priority_date) dates.priority_date = m[1];
                    }
                    return dates;
                }
                """)
                result['dates'] = js_dates or {}
            except:
                result['dates'] = {}
            
            # === 3. 申請人 ===
            assignee_match = re.search(r'Assignee[s]?:\s*(.+?)(?:\n|Inventor)', text, re.IGNORECASE)
            result['assignee'] = assignee_match.group(1).strip()[:200] if assignee_match else ''
            
            # === 4. CPC ===
            cpc_matches = re.findall(r'C09K19/\d+', text)
            result['cpc_codes'] = list(set(cpc_matches))[:5]
            
            # === 5. Abstract ===
            abs_match = re.search(r'Abstract[^\n]*\n\s*(.+?)(?=\n\n|\nDescription|\nClaims)', text, re.DOTALL | re.IGNORECASE)
            result['abstract'] = abs_match.group(1).strip()[:2000] if abs_match else ''
            
            # === 6. Claim 1 ===
            claim1 = None
            claim_patterns = [
                r'WHAT\s+IS\s+CLAIMED\s+IS\s*:?\s*1\.\s*([\s\S]{50,}?)(?=\n\s*2\.\s)',
                r'CLAIMS\s*\n\s*1\.\s*([\s\S]{50,}?)(?=\n\s*2\.\s)',
                r'1\.\s+([A-Z][\s\S]{50,5000}?)(?=\n\s*2\.\s)',
                r'(?:Claim|claim)\s*1\s*[.:]\s*([\s\S]{50,5000}?)(?=(?:Claim|claim)\s*2|\Z)',
            ]
            claims_section = re.search(r'(?:WHAT\s+IS\s+CLAIMED|CLAIMS|權利要求)', text, re.IGNORECASE)
            search_text = text[claims_section.start():] if claims_section else text
            for pat in claim_patterns:
                m = re.search(pat, search_text, re.IGNORECASE)
                if m and len(m.group(1).strip()) >= 50:
                    claim1 = re.sub(r'\s+', ' ', m.group(1).strip())
                    break
            result['claim1'] = claim1
            result['claim1_length'] = len(claim1) if claim1 else 0
            
            # === 7. 負介電確認 ===
            neg_kw = ['negative dielectric anisotropy', 'negative dielectric', 'Δε', 'Δε <', 'Δε = -',
                      'dielectric anisotropy of', 'negative Δε', 'lateral fluorine', 'difluoro']
            pos_kw = ['positive dielectric anisotropy', 'positive dielectric', 'Δε >', 'Δε = +']
            neg_count = sum(text.lower().count(kw.lower()) for kw in neg_kw)
            pos_count = sum(text.lower().count(kw.lower()) for kw in pos_kw)
            result['negative_dielectric_count'] = neg_count
            result['positive_dielectric_count'] = pos_count
            result['is_negative_dielectric'] = neg_count > pos_count
            
            # Also check Δε values
            delta_eps_matches = re.findall(r'Δε\s*[=:≈]\s*[-–]?(\d+\.?\d*)', text)
            result['delta_eps_values'] = delta_eps_matches[:5]
            
            # === 8. Contrast 相關段落 ===
            contrast_snippets = []
            for kw in ['contrast ratio', 'high contrast', 'contrast improvement', 
                       'improved contrast', 'enhanced contrast', 'contrast of', 
                       'low contrast', 'optical contrast', 'on-off contrast',
                       'voltage holding ratio', 'VHR', 'response time', 'transmittance']:
                for m in re.finditer(rf'(.{{0,80}}{re.escape(kw)}.{{0,120}})', text, re.IGNORECASE):
                    snippet = m.group(0).strip().replace('\n', ' ')
                    if len(snippet) > 30 and snippet not in contrast_snippets:
                        contrast_snippets.append(snippet)
            result['contrast_snippets'] = contrast_snippets[:15]
            result['contrast_keyword_count'] = len(contrast_snippets)
            
            # === 9. 混合實施例 + 物理參數 ===
            # Extract mixture examples (M1, M2, etc.)
            mixture_examples = []
            mix_pattern = r'(?:Mixture\s+Example|Mixture)\s+(M\d+|P\d+)\s*\n([\s\S]{100,1500}?)(?=\n\s*(?:Mixture\s+Example|Mixture)\s+(?:M|P)\d+|\n\s*Claims|\n\s*Description|$)'
            for m in re.finditer(mix_pattern, text, re.IGNORECASE):
                mix_name = m.group(1)
                mix_content = m.group(2).strip()[:800]
                mixture_examples.append({'name': mix_name, 'content': mix_content})
            result['mixture_examples'] = mixture_examples[:10]
            
            # Extract physical parameters
            phys_params = {}
            param_patterns = [
                (r'Cl\.?\s*p\.?\s*\[?°C?\]?:?\s*([\d.]+)', 'clearing_point'),
                (r'Δn\s*\[?589\s*nm[^)]*\)?:?\s*([\d.]+)', 'delta_n'),
                (r'Δε\s*\[?1\s*kHz[^)]*\)?:?\s*[-–]?([\d.]+)', 'delta_epsilon'),
                (r'ε∥\s*\[?1\s*kHz[^)]*\)?:?\s*([\d.]+)', 'epsilon_parallel'),
                (r'ε⊥\s*\[?1\s*kHz[^)]*\)?:?\s*([\d.]+)', 'epsilon_perpendicular'),
                (r'γ1\s*\[?mPa[^)]*\)?:?\s*([\d.]+)', 'gamma1'),
                (r'K1\s*\[?pN[^)]*\)?:?\s*([\d.]+)', 'K1'),
                (r'K3\s*\[?pN[^)]*\)?:?\s*([\d.]+)', 'K3'),
                (r'V0\s*\[?V[^)]*\)?:?\s*([\d.]+)', 'V0'),
                (r'VHR\s*[=:]\s*([\d.]+)\s*%?', 'VHR'),
            ]
            for pat, key in param_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    phys_params[key] = m.group(1)
            result['phys_params'] = phys_params
            
            # === 10. 分子結構代碼 ===
            # Merck LC codes: CC-3-V, CPY-3-O2, B(S)-2O-O5, PY-3-O2, etc.
            mol_codes = re.findall(r'\b([A-Z]{1,4}(?:\([^)]*\))?(?:-\d+){1,3}(?:-[A-Z]\d?)*)\b', text)
            # Filter for known LC code patterns
            lc_prefixes = ['CC', 'CP', 'CY', 'PY', 'PP', 'BCH', 'CCH', 'PCH', 'B(S)', 'B-',
                           'CCP', 'CCY', 'CPY', 'PYP', 'PGI', 'PGP', 'CLU', 'CDU', 'DGU', 'PGU', 'PPG', 'PUS',
                           'RM', 'ST', 'LB', 'CLY', 'CLP', 'CGP', 'CCC', 'CCV', 'APU', 'LB(S)']
            filtered_mols = []
            seen_mols = set()
            for code in mol_codes:
                for prefix in lc_prefixes:
                    if code.startswith(prefix) and code not in seen_mols and len(code) >= 5:
                        seen_mols.add(code)
                        filtered_mols.append(code)
                        break
            result['molecular_structures'] = filtered_mols[:30]
            
            result['success'] = True
            result['text_length'] = len(text)
            page.close()
            
        except Exception as e:
            result['error'] = str(e)
        finally:
            browser.close()
    
    return result


def main():
    # Load search results
    search_file = os.path.join(REPORTS_DIR, 'contrast_focused_v2.json')
    with open(search_file) as f:
        search_data = json.load(f)
    
    patent_ids = search_data.get('patent_ids', [])
    # Remove duplicates (some are EP without A1 suffix)
    clean_ids = []
    seen_normalized = set()
    for pid in patent_ids:
        # Normalize: strip trailing A1/B2 for dedup
        norm = re.sub(r'[A-Z]\d?$', '', pid)
        if norm not in seen_normalized:
            seen_normalized.add(norm)
            clean_ids.append(pid)
    
    print(f"提取 {len(clean_ids)} 篇專利（去重後）")
    print("=" * 80)
    
    # Check already extracted (from previous runs)
    output_file = os.path.join(REPORTS_DIR, 'contrast_deep_extract_v2.json')
    already_done = {}
    if os.path.exists(output_file):
        with open(output_file) as f:
            prev = json.load(f)
        for item in prev:
            if isinstance(item, dict) and item.get('success'):
                already_done[item['patent_id']] = item
        print(f"已有 {len(already_done)} 篇提取數據")
    
    extracted = list(already_done.values()) if already_done else []
    stats = {'total': 0, 'success': 0, 'claim1': 0, 'contrast': 0, 'negDA': 0, 'phys': 0}
    
    for i, pid in enumerate(clean_ids, 1):
        if pid in already_done:
            print(f"[{i}/{len(clean_ids)}] {pid} — 已提取，跳過")
            continue
        
        print(f"[{i}/{len(clean_ids)}] 提取 {pid}...")
        result = extract_patent_deep(pid)
        stats['total'] += 1
        
        if result.get('success'):
            stats['success'] += 1
            if result.get('claim1'):
                stats['claim1'] += 1
            if result.get('contrast_keyword_count', 0) > 0:
                stats['contrast'] += 1
            if result.get('is_negative_dielectric'):
                stats['negDA'] += 1
            if result.get('phys_params'):
                stats['phys'] += 1
            print(f"  ✓ {result['title'][:50]} | C1:{result['claim1_length']}ch | "
                  f"neg:{result['negative_dielectric_count']}/pos:{result['positive_dielectric_count']} | "
                  f"contrast:{result['contrast_keyword_count']} | phys:{len(result['phys_params'])} | "
                  f"FD:{result.get('dates',{}).get('filing_date','?')}")
        else:
            print(f"  ✗ 失敗: {result.get('error','?')}")
        
        extracted.append(result)
        time.sleep(1.5)
        
        # Save incremental
        if stats['total'] % 3 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted, f, ensure_ascii=False, indent=2)
    
    # Final save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)
    
    # Print summary
    n = max(stats['total'], 1)
    print(f"\n{'='*60}")
    print(f"提取統計:")
    print(f"  成功: {stats['success']}/{stats['total']}")
    print(f"  Claim1: {stats['claim1']}/{stats['total']}")
    print(f"  有 contrast 關鍵字: {stats['contrast']}/{stats['total']}")
    print(f"  負介電: {stats['negDA']}/{stats['total']}")
    print(f"  有物理參數: {stats['phys']}/{stats['total']}")
    print(f"  結果: {output_file}")
    
    return extracted


if __name__ == '__main__':
    main()

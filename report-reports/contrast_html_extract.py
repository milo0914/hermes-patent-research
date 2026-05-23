#!/usr/bin/env python3
"""Raw HTML extract - parse Google Patents page source directly for full data"""
import sys, json, re, time, subprocess
sys.stdout.reconfigure(line_buffering=True)

HTML_SCRIPT = r'''#!/usr/bin/env python3
import sys, json, re
sys.stdout.reconfigure(line_buffering=True)
from playwright.sync_api import sync_playwright

pid = sys.argv[1]
url = f"https://patents.google.com/patent/{pid}/en"

result = {"patent_id": pid, "success": False}

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(4000)
        
        for i in range(8):
            page.evaluate("window.scrollBy(0, 2500)")
            page.wait_for_timeout(1000)
        
        # Get raw HTML
        html = page.content()
        
        # 1. Title: from <title> or <meta> tags
        title = ''
        title_m = re.search(r'<title[^>]*>(.*?)\s*-\s*Google Patents', html)
        if title_m:
            title = title_m.group(1).strip()
        if not title:
            title_m2 = re.search(r'<meta\s+name="dc\.title"\s+content="([^"]+)"', html)
            if title_m2:
                title = title_m2.group(1).strip()
        if not title:
            title_m3 = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
            if title_m3:
                title = title_m3.group(1).strip()
        # Try invention-title class
        if not title:
            title_m4 = re.search(r'class="invention-title"[^>]*>(.*?)</', html, re.DOTALL)
            if title_m4:
                title = re.sub(r'<[^>]+>', '', title_m4.group(1)).strip()
        if not title:
            title_m5 = re.search(r'class="title"[^>]*>(.*?)</', html, re.DOTALL)
            if title_m5:
                title = re.sub(r'<[^>]+>', '', title_m5.group(1)).strip()
        
        # 2. Abstract: look for section with itemprop="abstract" or class="abstract"
        abstract = ''
        abs_m = re.search(r'itemprop="abstract"[^>]*>(.*?)</section>', html, re.DOTALL)
        if abs_m:
            abstract = re.sub(r'<[^>]+>', ' ', abs_m.group(1)).strip()[:2000]
        if not abstract:
            abs_m2 = re.search(r'class="abstract"[^>]*>(.*?)</div>', html, re.DOTALL)
            if abs_m2:
                abstract = re.sub(r'<[^>]+>', ' ', abs_m2.group(1)).strip()[:2000]
        
        # 3. Claim 1: find the first claim in HTML
        claim1 = ''
        # Try claim-text class or itemprop claims
        claim_m = re.search(r'itemprop="claims"[^>]*>.*?<div[^>]*class="claim-text"[^>]*>(.*?)</div>', html, re.DOTALL)
        if claim_m:
            claim1 = re.sub(r'<[^>]+>', ' ', claim_m.group(1)).strip()[:4000]
        if not claim1:
            # Try num="1" attribute
            claim_m2 = re.search(r'num="1"[^>]*>(.*?)</claim>', html, re.DOTALL)
            if claim_m2:
                claim1 = re.sub(r'<[^>]+>', ' ', claim_m2.group(1)).strip()[:4000]
        if not claim1:
            # Broader: find first claim-text div
            claim_m3 = re.search(r'class="claim-text"[^>]*>(.*?)</div>', html, re.DOTALL)
            if claim_m3:
                claim1 = re.sub(r'<[^>]+>', ' ', claim_m3.group(1)).strip()[:4000]
        if not claim1:
            # Try claim class
            claim_m4 = re.search(r'class="claim"[^>]*>(.*?)(?=class="claim")', html, re.DOTALL)
            if claim_m4:
                claim1 = re.sub(r'<[^>]+>', ' ', claim_m4.group(1)).strip()[:4000]
        if not claim1:
            # Fallback: text search in body
            body = page.inner_text('body')
            claim_patterns = [
                r'WHAT IS CLAIMED IS:\s*1\.\s+([\s\S]{30,4000}?)(?:\n\s*2\.|Claims\b|DESCRIPTION\b)',
                r'CLAIMS\s*1\.\s+([\s\S]{30,4000}?)(?:\n\s*2\.|Claims\b|DESCRIPTION\b)',
                r'1\.\s+(?:A|An|The)\s+([\s\S]{30,4000}?)(?:\n\s*2\.|Claims\b)',
            ]
            for pat in claim_patterns:
                m = re.search(pat, body)
                if m:
                    claim1 = m.group(1).strip().replace('\n', ' ')[:4000]
                    break
        
        # 4. Dates from timeline in HTML
        dates = {}
        # Timeline events contain date + event type
        timeline_matches = re.findall(r'class="event[^"]*"[^>]*>.*?(\d{4}-\d{2}-\d{2}).*?</div>', html, re.DOTALL)
        # Also try broader pattern
        all_timeline = re.findall(r'application-timeline.*?(\d{4}-\d{2}-\d{2})\s*(.*?)<', html, re.DOTALL)
        for d, desc in all_timeline:
            desc_lower = desc.lower()
            if 'filed' in desc_lower:
                dates['filing_date'] = d
            elif 'published' in desc_lower or 'publication' in desc_lower:
                dates['publication_date'] = d
            elif 'granted' in desc_lower:
                dates['grant_date'] = d
            elif 'priority' in desc_lower:
                dates['priority_date'] = d
        
        # 5. Full description from HTML
        desc = ''
        desc_m = re.search(r'itemprop="description"[^>]*>(.*?)</section>', html, re.DOTALL)
        if desc_m:
            desc = re.sub(r'<[^>]+>', ' ', desc_m.group(1)).strip()[:40000]
        if not desc:
            desc_m2 = re.search(r'class="description"[^>]*>(.*?)</section>', html, re.DOTALL)
            if desc_m2:
                desc = re.sub(r'<[^>]+>', ' ', desc_m2.group(1)).strip()[:40000]
        if not desc:
            body = page.inner_text('body')
            desc_m3 = re.search(r'Description\s*\n([\s\S]{200,}?)\n\s*Claims\b', body, re.IGNORECASE)
            if desc_m3:
                desc = desc_m3.group(1).strip()[:40000]
        
        # 6. Neg/pos DA in description
        neg_count = len(re.findall(r'negative\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        pos_count = len(re.findall(r'positive\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        
        # 7. Contrast
        contrast_count = len(re.findall(r'contrast', desc, re.IGNORECASE))
        contrast_ratio_count = len(re.findall(r'contrast\s+ratio', desc, re.IGNORECASE))
        high_contrast_count = len(re.findall(r'high\s+contrast', desc, re.IGNORECASE))
        
        # 8. Examples
        examples = []
        ex_parts = re.split(r'(?=((?:Working\s+)?(?:Example|EXAMPLE|Comparative)\s*\d+))', desc)
        for i in range(1, min(len(ex_parts), 31), 2):
            if i+1 < len(ex_parts):
                header = ex_parts[i].strip()[:100]
                text = ex_parts[i+1].strip()[:500]
                examples.append({'header': header, 'text': text})
        
        # If no examples from split, try direct pattern
        if not examples:
            ex_matches = re.findall(r'((?:Working\s+)?(?:Example|EXAMPLE|Comparative)\s*\d+[.:]\s*.{0,400})', desc)
            examples = [{'header': m[:50], 'text': m} for m in ex_matches[:15]]
        
        # 9. Molecular structure references
        mol_structs = []
        formula_matches = re.findall(r'(?:of\s+)?formula\s+[IVX]+\s*[^.;]{0,200}', desc, re.IGNORECASE)
        seen = set()
        for m in formula_matches:
            m_clean = m.strip()[:200]
            if m_clean not in seen and len(m_clean) > 15:
                seen.add(m_clean)
                mol_structs.append(m_clean)
        
        # 10. Physical data
        phys_data = {}
        de_matches = re.findall(r'[Δd][eε]\s*[=≈~:]\s*([-+]?[\d.]+)', desc)
        if de_matches: phys_data['delta_epsilon'] = de_matches[:10]
        dn_matches = re.findall(r'Δn\s*[=≈~:]\s*([\d.]+)', desc)
        if dn_matches: phys_data['delta_n'] = dn_matches[:10]
        cp_matches = re.findall(r'(?:clearing\s+point|T\(N,I?\))\s*[=≈~:]\s*([\d.]+)\s*°?C?', desc, re.IGNORECASE)
        if cp_matches: phys_data['clearing_point'] = cp_matches[:5]
        cr_matches = re.findall(r'contrast\s*(?:ratio)?\s*[=≈~:]\s*([\d.]+)', desc, re.IGNORECASE)
        if cr_matches: phys_data['contrast_ratio'] = cr_matches[:10]
        vhr_matches = re.findall(r'VHR\s*[=≈~:]\s*([\d.]+)', desc)
        if vhr_matches: phys_data['VHR'] = vhr_matches[:10]
        vth_matches = re.findall(r'(?:Vth|Vth,?)\s*[=≈~:]\s*([\d.]+)', desc, re.IGNORECASE)
        if vth_matches: phys_data['Vth'] = vth_matches[:10]
        
        # is_negative_dielectric
        is_neg_da = None
        if neg_count > 0 and neg_count >= pos_count:
            is_neg_da = True
        elif pos_count > 0 and neg_count == 0:
            is_neg_da = False
        elif neg_count > 0:
            is_neg_da = True
        
        result.update({
            'success': True,
            'title': title,
            'abstract': abstract[:2000],
            'claim1': claim1,
            'claim1_length': len(claim1),
            'dates': dates,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_dielectric': is_neg_da,
            'contrast_count': contrast_count,
            'contrast_ratio_count': contrast_ratio_count,
            'high_contrast_count': high_contrast_count,
            'examples': examples[:15],
            'example_count': len(examples),
            'molecular_structures': mol_structs[:15],
            'phys_data': phys_data,
            'desc_length': len(desc),
            'html_length': len(html)
        })
        
        browser.close()

except Exception as e:
    result['error'] = str(e)
    import traceback
    result['traceback'] = traceback.format_exc()

print(json.dumps(result, ensure_ascii=False))
'''

script_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/html_extract_patent.py'
with open(script_path, 'w', encoding='utf-8') as f:
    f.write(HTML_SCRIPT)

PIDS = [
    "US12528988B2", "US20250101305A1", "US20250136868A1", "US20250154412A1",
    "US20250189829A1", "US20250197723A1", "US20250207032A1", "US20250215323A1",
    "US20250223496A1", "US20250277152A1", "US20250284151A1", "US20250361444A1",
    "US20260015735A1"
]

all_results = []
for i, pid in enumerate(PIDS):
    print(f"\n[{i+1}/{len(PIDS)}] HTML extracting {pid}...")
    try:
        proc = subprocess.run(
            ['python3', '-u', script_path, pid],
            capture_output=True, text=True, timeout=100
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        all_results.append(data)
                        print(f"  title: {data.get('title','')[:80]}")
                        print(f"  abstract: {len(data.get('abstract',''))} chars")
                        print(f"  claim1: {data.get('claim1_length',0)} chars")
                        print(f"  neg/pos: {data.get('neg_da_count',0)}/{data.get('pos_da_count',0)} is_neg={data.get('is_negative_dielectric')}")
                        print(f"  contrast: {data.get('contrast_count',0)} (ratio:{data.get('contrast_ratio_count',0)}, high:{data.get('high_contrast_count',0)})")
                        print(f"  examples: {data.get('example_count',0)}")
                        print(f"  mol: {len(data.get('molecular_structures',[]))}")
                        print(f"  phys: {list(data.get('phys_data',{}).keys())}")
                        print(f"  dates: {data.get('dates',{})}")
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                all_results.append({'patent_id': pid, 'success': False})
        else:
            err = proc.stderr[:300]
            print(f"  Error: {err}")
            all_results.append({'patent_id': pid, 'success': False, 'error': err})
    except subprocess.TimeoutExpired:
        print(f"  Timeout")
        all_results.append({'patent_id': pid, 'success': False, 'error': 'Timeout'})

out_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_html_extract_all.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

ok_count = sum(1 for r in all_results if r.get('success'))
print(f"\nHTML extraction complete: {ok_count}/{len(all_results)} successful")

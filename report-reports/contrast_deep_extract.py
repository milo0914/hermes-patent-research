#!/usr/bin/env python3
"""Deep extract - title, abstract, claim1, examples, physical data for each patent"""
import sys, json, re, time, subprocess
sys.stdout.reconfigure(line_buffering=True)

DEEP_SCRIPT = r'''#!/usr/bin/env python3
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
        page.wait_for_timeout(3000)
        
        for i in range(8):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(1000)
        
        # Deep JS extraction for title, abstract, claims, dates
        deep = page.evaluate("""() => {
            const out = {title:'', abstract:'', claim1:'', dates:{}};
            
            // Title: try multiple selectors
            const titleSelectors = [
                'h1[itemprop="title"]', 'h1.title', 'h1',
                '[itemprop="name"]', '.invention-title',
                'meta[name="dc.title"]', 'meta[property="og:title"]'
            ];
            for (const sel of titleSelectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent && el.textContent.trim().length > 5) {
                    out.title = el.textContent.trim();
                    break;
                }
                if (el && el.content && el.content.trim().length > 5) {
                    out.title = el.content.trim();
                    break;
                }
            }
            
            // Abstract
            const absSelectors = [
                '[itemprop="abstract"]', '.abstract',
                'section.abstract', '[class*="abstract"]'
            ];
            for (const sel of absSelectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent && el.textContent.trim().length > 20) {
                    out.abstract = el.textContent.trim().substring(0, 2000);
                    break;
                }
            }
            
            // Claim 1
            const claimSelectors = [
                '[itemprop="claims"] [num="1"]',
                '[class*="claim"] [num="1"]',
                '[class*="claim-text"]',
                '.claim:nth-of-type(1)'
            ];
            for (const sel of claimSelectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent && el.textContent.trim().length > 20) {
                    out.claim1 = el.textContent.trim().substring(0, 4000);
                    break;
                }
            }
            
            // If no claim found, try getting all claim elements
            if (!out.claim1) {
                const claims = document.querySelectorAll('[class*="claim"]');
                if (claims.length > 0) {
                    out.claim1 = claims[0].textContent.trim().substring(0, 4000);
                }
            }
            
            // Dates from timeline
            const timelineEls = document.querySelectorAll('.event.style-scope.application-timeline, [class*="timeline"] [class*="event"]');
            for (const el of timelineEls) {
                const txt = el.textContent.trim();
                const dm = txt.match(/(\\d{4}-\\d{2}-\\d{2})\\s+(.*)/);
                if (dm) {
                    const d = dm[1], desc = dm[2].toLowerCase();
                    if (desc.includes('filed')) out.dates.filing_date = d;
                    else if (desc.includes('published') || desc.includes('publication')) out.dates.publication_date = d;
                    else if (desc.includes('granted')) out.dates.grant_date = d;
                    else if (desc.includes('priority')) out.dates.priority_date = d;
                }
            }
            
            return out;
        }""")
        
        result['title'] = deep.get('title', '')
        result['abstract'] = deep.get('abstract', '')
        result['claim1'] = deep.get('claim1', '')
        result['claim1_length'] = len(deep.get('claim1', ''))
        result['dates'] = deep.get('dates', {})
        
        # If title still empty, try from page title / URL
        if not result['title']:
            page_title = page.title()
            if page_title and 'Google Patents' in page_title:
                result['title'] = page_title.replace(' - Google Patents', '').replace('Google Patents', '').strip()
        
        # Full body for examples and physical data
        body = page.inner_text('body')
        
        # Description section
        desc = ''
        desc_m = re.search(r'Description\s*\n([\s\S]{200,}?)\n\s*Claims\b', body, re.IGNORECASE)
        if desc_m:
            desc = desc_m.group(1).strip()[:30000]
        else:
            desc = body[3000:33000] if len(body) > 33000 else body[3000:]
        
        # Neg/pos DA
        neg_count = len(re.findall(r'negative\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        pos_count = len(re.findall(r'positive\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        
        # Contrast
        contrast_count = len(re.findall(r'contrast', desc, re.IGNORECASE))
        contrast_ratio_count = len(re.findall(r'contrast\s+ratio', desc, re.IGNORECASE))
        high_contrast_count = len(re.findall(r'high\s+contrast', desc, re.IGNORECASE))
        
        # Examples - try broader patterns
        examples = []
        # Pattern: "Example N" followed by text until next "Example" or section
        ex_sections = re.split(r'(?=(?:Working\s+)?(?:Example|EXAMPLE|Comparative)\s*\d+)', desc)
        for sec in ex_sections[1:16]:  # skip first (before any example)
            # Extract example number and text
            header_m = re.match(r'((?:Working\s+)?(?:Example|EXAMPLE|Comparative)\s*(\d+))\s*[.:]?\s*(.{0,500})', sec, re.DOTALL)
            if header_m:
                examples.append({
                    'header': header_m.group(1).strip(),
                    'num': header_m.group(2),
                    'text': header_m.group(3).strip()[:400]
                })
        
        # If still no examples, try table-based extraction
        if not examples:
            # Look for "Table" mentions with performance data
            table_refs = re.findall(r'(?:Table|TABLE)\s*(\d+)[.:]?\s*(.{0,300})', desc)
            for num, text in table_refs[:10]:
                examples.append({
                    'header': f'Table {num}',
                    'num': num,
                    'text': text.strip()[:400]
                })
        
        # Molecular structures
        mol_structs = []
        formula_matches = re.findall(r'(?:of\s+)?formula\s+[IVX]+\s*[^.;]{0,200}', desc, re.IGNORECASE)
        seen = set()
        for m in formula_matches:
            m_clean = m.strip()[:200]
            if m_clean not in seen and len(m_clean) > 15:
                seen.add(m_clean)
                mol_structs.append(m_clean)
        
        # Physical data - numerical values near keywords
        phys_data = {}
        # delta-epsilon
        de_matches = re.findall(r'[Δd][eε]\s*[=≈~:]\s*([-+]?[\d.]+)', desc)
        if de_matches:
            phys_data['delta_epsilon'] = de_matches[:10]
        # delta-n
        dn_matches = re.findall(r'Δn\s*[=≈~:]\s*([\d.]+)', desc)
        if dn_matches:
            phys_data['delta_n'] = dn_matches[:10]
        # Clearing point
        cp_matches = re.findall(r'(?:clearing\s+point|T\(N,I?\))\s*[=≈~:]\s*([\d.]+)\s*°?C?', desc, re.IGNORECASE)
        if cp_matches:
            phys_data['clearing_point'] = cp_matches[:5]
        # Contrast ratio values (numerical)
        cr_matches = re.findall(r'contrast\s*(?:ratio)?\s*[=≈~:]\s*([\d.]+)', desc, re.IGNORECASE)
        if cr_matches:
            phys_data['contrast_ratio'] = cr_matches[:10]
        # VHR
        vhr_matches = re.findall(r'VHR\s*[=≈~:]\s*([\d.]+)', desc)
        if vhr_matches:
            phys_data['VHR'] = vhr_matches[:10]
        # Threshold voltage
        vth_matches = re.findall(r'(?:Vth|V(?:th|0|th,?))\s*[=≈~:]\s*([\d.]+)\s*V?', desc, re.IGNORECASE)
        if vth_matches:
            phys_data['Vth'] = vth_matches[:10]
        # Response time
        rt_matches = re.findall(r'(?:response\s+time|τ)\s*[=≈~:]\s*([\d.]+)\s*ms?', desc, re.IGNORECASE)
        if rt_matches:
            phys_data['response_time'] = rt_matches[:10]
        
        # Determine is_negative_dielectric
        is_neg_da = None
        if neg_count > 0 and neg_count >= pos_count:
            is_neg_da = True
        elif pos_count > 0 and neg_count == 0:
            is_neg_da = False
        elif neg_count > 0:
            is_neg_da = True
        
        result.update({
            'success': True,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_dielectric': is_neg_da,
            'contrast_count': contrast_count,
            'contrast_ratio_count': contrast_ratio_count,
            'high_contrast_count': high_contrast_count,
            'examples': examples,
            'example_count': len(examples),
            'molecular_structures': mol_structs[:15],
            'phys_data': phys_data,
            'desc_length': len(desc),
            'body_length': len(body)
        })
        
        browser.close()

except Exception as e:
    result['error'] = str(e)
    import traceback
    result['traceback'] = traceback.format_exc()

print(json.dumps(result, ensure_ascii=False))
'''

script_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/deep_extract_patent.py'
with open(script_path, 'w', encoding='utf-8') as f:
    f.write(DEEP_SCRIPT)

# All US patents
PIDS = [
    "US12528988B2", "US20250101305A1", "US20250136868A1", "US20250154412A1",
    "US20250189829A1", "US20250197723A1", "US20250207032A1", "US20250215323A1",
    "US20250223496A1", "US20250277152A1", "US20250284151A1", "US20250361444A1",
    "US20260015735A1"
]

all_results = []
for i, pid in enumerate(PIDS):
    print(f"\n[{i+1}/{len(PIDS)}] Deep extracting {pid}...")
    try:
        proc = subprocess.run(
            ['python3', '-u', script_path, pid],
            capture_output=True, text=True, timeout=90
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        all_results.append(data)
                        print(f"  title: {data.get('title','')[:70]}")
                        print(f"  abstract: {len(data.get('abstract',''))} chars")
                        print(f"  claim1: {data.get('claim1_length',0)} chars")
                        print(f"  neg/pos: {data.get('neg_da_count',0)}/{data.get('pos_da_count',0)} is_neg={data.get('is_negative_dielectric')}")
                        print(f"  contrast: total={data.get('contrast_count',0)} ratio={data.get('contrast_ratio_count',0)} high={data.get('high_contrast_count',0)}")
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
            print(f"  Error: {proc.stderr[:200]}")
            all_results.append({'patent_id': pid, 'success': False, 'error': proc.stderr[:200]})
    except subprocess.TimeoutExpired:
        print(f"  Timeout")
        all_results.append({'patent_id': pid, 'success': False, 'error': 'Timeout'})

out_path = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_deep_extract_all.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

ok_count = sum(1 for r in all_results if r.get('success'))
print(f"\nDeep extraction complete: {ok_count}/{len(all_results)} successful")

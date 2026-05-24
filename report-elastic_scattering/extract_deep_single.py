#!/usr/bin/env python3
import json, re, os, sys
from playwright.sync_api import sync_playwright

PID = sys.argv[1]
OUT_DIR = sys.argv[2]
url = f'https://patents.google.com/patent/{PID}/en'

result = {'patent_id': PID, 'title': '', 'abstract': '', 'claim1': '',
          'filing_date': '', 'priority_date': '', 'publication_date': '',
          'neg_da_count': 0, 'pos_da_count': 0, 'is_negative_da': None,
          'neg_da_evidence': [], 'elastic_hits': [], 'scattering_hits': [],
          'physical_params_raw': '', 'example_table_data': '',
          'description_neg_da_section': ''}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
    page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(3000)
        body = page.inner_text('body')
        
        # Title
        import re as re_mod
        title_m = re_mod.search(r'(.+?)\s*-\s*Google Patents', page.title())
        result['title'] = title_m.group(1).strip() if title_m else page.title().strip()
        
        # Dates from timeline
        try:
            events = page.evaluate("""() => {
                const items = document.querySelectorAll('.event.style-scope.application-timeline');
                return Array.from(items).map(e => e.textContent.trim().substring(0, 200));
            }""")
            for evt in events:
                dm = re_mod.match(r'(\d{4}-\d{2}-\d{2})\s+(.*)', evt)
                if dm:
                    d, desc = dm.group(1), dm.group(2).lower()
                    if 'filed' in desc and not result['filing_date']:
                        result['filing_date'] = d
                    elif 'priority' in desc and not result['priority_date']:
                        result['priority_date'] = d
                    elif 'publication' in desc or 'published' in desc:
                        result['publication_date'] = d
        except: pass
        
        # Abstract
        abs_m = re_mod.search(r'Abstract\n([\s\S]{30,3000}?)\nClassifications', body)
        if abs_m:
            result['abstract'] = abs_m.group(1).strip()[:1500]
        
        # Full body for deep analysis (up to 200K chars)
        full_body = body[:200000]
        
        # Claim 1 - multiple patterns
        claim_patterns = [
            r'WHAT IS CLAIMED IS:\s*1\.\s+([\s\S]{10,5000}?)(?:\n2\.|Claims\n)',
            r'CLAIMS\s*1\.\s+([\s\S]{10,5000}?)(?:\n2\.|Claims\n)',
            r'1\.\s+([\s\S]{10,5000}?)(?:\n2\.|Claims\n)',
        ]
        for cp in claim_patterns:
            cm = re_mod.search(cp, body)
            if cm and len(cm.group(1).strip()) > 50:
                result['claim1'] = re_mod.sub(r'\s+', ' ', cm.group(1).strip())[:5000]
                break
        
        # EP DOM fallback
        if not result['claim1'] and PID.startswith('EP'):
            try:
                js_result = page.evaluate("""() => {
                    const claims = [];
                    const ol = document.querySelector('ol.claims');
                    if (ol) {
                        const items = ol.querySelectorAll('li.claim');
                        items.forEach((li, idx) => {
                            claims.push({num: idx+1, text: li.innerText.trim()});
                        });
                    }
                    return {claims: claims};
                }""")
                for c in js_result.get('claims', []):
                    if c['num'] == 1 and c['text']:
                        result['claim1'] = re_mod.sub(r'\s+', ' ', c['text'])[:5000]
            except: pass
        
        # Description
        desc_m = re_mod.search(r'Description\n([\s\S]{200,}?)\nClaims', body)
        if desc_m:
            result['description'] = desc_m.group(1).strip()[:50000]
        
        # === DEEP NEG DA ANALYSIS ===
        # Search for negative DA evidence in multiple ways
        neg_patterns = [
            r'negative\s+dielectric\s+anisotrop',
            r'Δε\s*[<≤]\s*0',
            r'dielectric\s+anisotropy\s*Δε.*?negative',
            r'compound[s]?\s+having\s+negative\s+dielectric',
            r'component\s*[AB]\s*.*?negative\s+dielectric',
            r'Δε\s*=\s*-[\d.]+',
        ]
        for np in neg_patterns:
            hits = list(re_mod.finditer(np, full_body, re_mod.IGNORECASE))
            for h in hits[:3]:
                ctx = full_body[max(0,h.start()-120):h.end()+120].replace('\n',' ')
                result['neg_da_evidence'].append({'pattern': np, 'context': ctx})
        
        result['neg_da_count'] = len(re_mod.findall(r'negative\s+dielectric\s+anisotrop', full_body, re_mod.IGNORECASE))
        result['pos_da_count'] = len(re_mod.findall(r'positive\s+dielectric\s+anisotrop', full_body, re_mod.IGNORECASE))
        
        # Final determination
        c1_lower = result.get('claim1', '').lower()
        abs_lower = result.get('abstract', '').lower()
        
        # Key: does abstract or claim1 explicitly say negative DA?
        explicit_neg = 'negative dielectric' in (c1_lower + abs_lower)
        neg_dominant = result['neg_da_count'] > result['pos_da_count']
        
        if explicit_neg or neg_dominant:
            result['is_negative_da'] = True
        elif result['pos_da_count'] > 0 and result['neg_da_count'] == 0:
            result['is_negative_da'] = False
        elif result['neg_da_count'] > 0:
            # Has both - check if abstract says "positive DA" (medium type) vs mentions neg DA compounds
            if 'positive dielectric anisotropy' in abs_lower and 'negative dielectric' not in abs_lower:
                result['is_negative_da'] = False  # Medium is pos DA but uses neg DA compounds as components
            else:
                result['is_negative_da'] = True  # Likely a neg DA medium
        else:
            result['is_negative_da'] = None
        
        # Elastic/scattering hits
        for kw in ['elastic constant', 'K33', 'K11', 'K22', 'elastic constants', 'K33/K11', 'bend elastic', 'splay elastic']:
            hits = list(re_mod.finditer(kw, full_body, re_mod.IGNORECASE))
            for h in hits[:5]:
                ctx = full_body[max(0,h.start()-100):h.end()+100].replace('\n',' ')
                result['elastic_hits'].append({kw: ctx})
        
        for kw in ['scattering', 'low scattering', 'light scattering', 'haze', 'forward scattering']:
            hits = list(re_mod.finditer(kw, full_body, re_mod.IGNORECASE))
            for h in hits[:5]:
                ctx = full_body[max(0,h.start()-100):h.end()+100].replace('\n',' ')
                result['scattering_hits'].append({kw: ctx})
        
        # Physical parameters table extraction
        # Look for table-like data with K values
        table_matches = re_mod.findall(r'(?:K11|K22|K33|γ1|Δε|Δn|V0|c\.p\.)\s*[^\n]{0,200}', full_body)
        result['physical_params_raw'] = '\n'.join(table_matches[:30])
        
        # Example table data
        example_table = re_mod.findall(r'(?:Mixture|Example)\s+\d+[A-Z]?\s*[\s\S]{0,300}(?:K11|K33|Δε|γ1|V0)', full_body)
        result['example_table_data'] = '\n---\n'.join(example_table[:10])
        
    except Exception as e:
        result['error'] = str(e)
    finally:
        browser.close()

out_path = os.path.join(OUT_DIR, f'extract_deep_{PID}.json')
with open(out_path, 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

# Print summary
print(f"PID: {PID}")
print(f"Title: {result['title'][:80]}")
print(f"Filing: {result['filing_date']}, Priority: {result['priority_date']}")
print(f"Abstract[:300]: {result['abstract'][:300]}")
print(f"Claim1[:300]: {result['claim1'][:300]}")
print(f"Neg/Pos DA: {result['neg_da_count']}/{result['pos_da_count']} -> is_neg={result['is_negative_da']}")
print(f"Neg DA evidence: {len(result['neg_da_evidence'])}")
for ev in result['neg_da_evidence'][:3]:
    print(f"  {ev['pattern']}: ...{ev['context'][:150]}...")
print(f"Elastic hits: {len(result['elastic_hits'])}")
print(f"Scattering hits: {len(result['scattering_hits'])}")
print(f"Params raw: {result['physical_params_raw'][:200]}")
print(f"Saved: {out_path}")

#!/usr/bin/env python3
"""Extract single patent - runs in isolated process"""
import sys, json, re, time, os

PATENT_ID = sys.argv[1]
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else '/tmp'

def extract_single(pid):
    from playwright.sync_api import sync_playwright
    
    # Build URL
    if pid.startswith('US'):
        url = f'https://patents.google.com/patent/{pid}/en'
    elif pid.startswith('EP'):
        url = f'https://patents.google.com/patent/{pid}/en'
    else:
        url = f'https://patents.google.com/patent/{pid}/en'
    
    result = {
        'patent_id': pid,
        'url': url,
        'title': '',
        'abstract': '',
        'claim1': '',
        'claim2': '',
        'description': '',
        'filing_date': '',
        'publication_date': '',
        'priority_date': '',
        'grant_date': '',
        'example_count': 0,
        'example_details': [],
        'molecular_codes': [],
        'physical_params': {},
        'neg_da_count': 0,
        'pos_da_count': 0,
        'is_negative_da': None,
        'elastic_hits': [],
        'scattering_hits': [],
        'body_length': 0,
        'error': None
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)
            
            # Get full body text
            body = page.inner_text('body')
            result['body_length'] = len(body)
            
            # === Title ===
            title_m = re.search(r'(.+?)\s*-\s*Google Patents', page.title())
            result['title'] = title_m.group(1).strip() if title_m else page.title().strip()
            
            # === Dates (from timeline events) ===
            try:
                events = page.evaluate("""() => {
                    const items = document.querySelectorAll('.event.style-scope.application-timeline');
                    return Array.from(items).map(e => e.textContent.trim().substring(0, 200));
                }""")
                for evt in events:
                    dm = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.*)', evt)
                    if dm:
                        d, desc = dm.group(1), dm.group(2).lower()
                        if 'filed' in desc and not result['filing_date']:
                            result['filing_date'] = d
                        elif 'priority' in desc and not result['priority_date']:
                            result['priority_date'] = d
                        elif 'publication' in desc or 'published' in desc:
                            if not result['publication_date']:
                                result['publication_date'] = d
                        elif 'grant' in desc or 'granted' in desc:
                            if not result['grant_date']:
                                result['grant_date'] = d
            except Exception as e:
                pass
            
            # Fallback: extract dates from body text
            if not result['filing_date']:
                dates = re.findall(r'\d{4}-\d{2}-\d{2}', body[:5000])
                if dates:
                    result['priority_date'] = dates[0]
                    if len(dates) > 1:
                        result['filing_date'] = dates[1]
            
            # === Abstract ===
            abs_m = re.search(r'Abstract\n([\s\S]{30,3000}?)\nClassifications', body)
            if abs_m:
                result['abstract'] = abs_m.group(1).strip()[:1500]
            
            # === Claims (try body text first) ===
            claim_patterns = [
                r'WHAT IS CLAIMED IS:\s*1\.\s+([\s\S]{10,3000}?)(?:\n2\.|Claims\n)',
                r'CLAIMS\s*1\.\s+([\s\S]{10,3000}?)(?:\n2\.|Claims\n)',
                r'1\.\s+([\s\S]{10,3000}?)(?:\n2\.|Claims\n)',
            ]
            for cp in claim_patterns:
                cm = re.search(cp, body)
                if cm and len(cm.group(1).strip()) > 50:
                    result['claim1'] = re.sub(r'\s+', ' ', cm.group(1).strip())[:3000]
                    break
            
            # Claim 2
            c2_m = re.search(r'(?:^|\n)2\.\s+([\s\S]{10,2000}?)(?:\n3\.|Claims\n)', body)
            if c2_m:
                result['claim2'] = re.sub(r'\s+', ' ', c2_m.group(1).strip())[:2000]
            
            # === Description ===
            desc_m = re.search(r'Description\n([\s\S]{200,}?)\nClaims', body)
            if desc_m:
                result['description'] = desc_m.group(1).strip()[:50000]
            
            # === EP Claims DOM fallback ===
            if pid.startswith('EP') and not result['claim1']:
                try:
                    js_result = page.evaluate("""() => {
                        const claims = [];
                        const claimList = document.querySelector('ol.claims, .claims');
                        if (claimList) {
                            const items = claimList.querySelectorAll('li.claim, li');
                            items.forEach((li, idx) => {
                                const text = li.innerText.trim();
                                if (text) claims.push({num: idx + 1, text: text});
                            });
                        }
                        if (claims.length === 0) {
                            const claimsSection = document.querySelector('section#claims');
                            if (claimsSection) {
                                const allText = claimsSection.innerText || '';
                                claims.push({num: 0, text: allText});
                            }
                        }
                        return {claims: claims};
                    }""")
                    for claim in js_result.get('claims', []):
                        num = claim.get('num', 0)
                        text = re.sub(r'\s+', ' ', claim.get('text', '')).strip()
                        if num == 1 and text:
                            result['claim1'] = text[:3000]
                        elif num == 2 and text:
                            result['claim2'] = text[:2000]
                except:
                    pass
            
            # === EP Description fallback ===
            if pid.startswith('EP') and not result['description']:
                try:
                    desc_data = page.evaluate("""() => {
                        const desc = document.querySelector('div.description');
                        if (desc) return desc.innerText;
                        const body = document.querySelector('div.publication-body');
                        if (body) return body.innerText;
                        return '';
                    }""")
                    if desc_data and len(desc_data) > 100:
                        result['description'] = desc_data[:50000]
                except:
                    pass
            
            # === Examples ===
            desc_text = result.get('description', '') or body
            example_patterns = [
                r'(?:Example|EXAMPLE|Mixture\s+Example)\s*[\s:]*(\d+[A-Z]?)\s*[:\.]?\s*([\s\S]{20,500}?)(?=(?:Example|EXAMPLE|Mixture\s+Example)\s*\d|$)',
                r'(?:Example|EXAMPLE)\s*(\d+)\s*[\s:]*([\s\S]{20,500}?)(?=(?:Example|EXAMPLE)\s*\d|$)',
            ]
            examples = []
            for ep in example_patterns:
                matches = re.findall(ep, desc_text, re.IGNORECASE)
                for m in matches:
                    if isinstance(m, tuple):
                        examples.append(f"Example {m[0]}: {m[1].strip()[:300]}")
                    else:
                        examples.append(m.strip()[:300])
            # Also count Example occurrences
            example_count = len(re.findall(r'\bExample\s+\d+', desc_text, re.IGNORECASE))
            example_count += len(re.findall(r'\bMixture\s+Example\s+[A-Z]?\d+', desc_text, re.IGNORECASE))
            result['example_count'] = max(example_count, len(examples))
            result['example_details'] = examples[:15]
            
            # === Molecular structure codes ===
            mol_codes = re.findall(r'\b([A-Z]{1,4}\(?[A-Z]?\)?-[\dO]+-[\dO]+[\w-]*)\b', body)
            mol_codes = list(set(m for m in mol_codes if len(m) > 3 and not m.startswith('US')))
            result['molecular_codes'] = sorted(mol_codes)[:50]
            
            # === Physical parameters ===
            param_patterns = {
                'delta_eps': r'[Δd]elta\s*[eε][∥⊥]?\s*[:：]?\s*([-\d.]+)',
                'delta_n': r'[Δd]elta\s*n\s*[:：]?\s*([-\d.]+)',
                'gamma1': r'[γg]1\s*[:：]?\s*([-\d.]+)',
                'K11': r'K11\s*[:：]?\s*([-\d.]+)',
                'K22': r'K22\s*[:：]?\s*([-\d.]+)',
                'K33': r'K33\s*[:：]?\s*([-\d.]+)',
                'V0': r'V0\s*[:：]?\s*([-\d.]+)',
                'eps_parallel': r'[εe][∥]\s*[:：]?\s*([-\d.]+)',
                'eps_perp': r'[εe][⊥]\s*[:：]?\s*([-\d.]+)',
            }
            for pname, pp in param_patterns.items():
                pm = re.search(pp, body, re.IGNORECASE)
                if pm:
                    result['physical_params'][pname] = pm.group(1)
            
            # Also extract elastic constant specific values from tables
            elastic_matches = re.findall(r'K(?:11|22|33)\s*(?:\[?[^\]]*\]?\s*)[:：]\s*([-\d.]+)\s*(?:pN|N|mN)?', body)
            if elastic_matches:
                result['physical_params']['elastic_values'] = elastic_matches[:10]
            
            # === Negative/Positive DA count ===
            result['neg_da_count'] = len(re.findall(r'negative\s+dielectric\s+anisotrop', body, re.IGNORECASE))
            result['pos_da_count'] = len(re.findall(r'positive\s+dielectric\s+anisotrop', body, re.IGNORECASE))
            neg_delta = len(re.findall(r'[Δd]elta\s*[eε]\s*[<≤-]\s*-?\d', body, re.IGNORECASE))
            
            if result['neg_da_count'] > 0 and (result['neg_da_count'] >= result['pos_da_count'] or neg_delta > 0):
                result['is_negative_da'] = True
            elif result['pos_da_count'] > 0 and result['neg_da_count'] == 0:
                result['is_negative_da'] = False
            else:
                result['is_negative_da'] = None
            
            # === Elastic constant keyword hits ===
            elastic_kw = ['elastic constant', 'elastic constants', 'K33', 'K11', 'K22', 
                          'bend elastic', 'splay elastic', 'twist elastic', 'K33/K11',
                          'elastic constant ratio', 'elastic ratio']
            for kw in elastic_kw:
                hits = [body[max(0,m.start()-80):m.end()+80].replace('\n',' ') 
                        for m in re.finditer(kw, body, re.IGNORECASE)]
                if hits:
                    result['elastic_hits'].extend([{kw: h} for h in hits[:5]])
            
            # === Scattering keyword hits ===
            scatter_kw = ['scattering', 'low scattering', 'light scattering', 'forward scattering',
                         'back scattering', 'scattering loss', 'haze', 'scatter']
            for kw in scatter_kw:
                hits = [body[max(0,m.start()-80):m.end()+80].replace('\n',' ') 
                        for m in re.finditer(kw, body, re.IGNORECASE)]
                if hits:
                    result['scattering_hits'].extend([{kw: h} for h in hits[:5]])
            
        except Exception as e:
            result['error'] = str(e)
        finally:
            browser.close()
    
    return result

# Run extraction
r = extract_single(PATENT_ID)

# Save to file
out_path = os.path.join(OUTPUT_DIR, f'extract_{PATENT_ID}.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(r, f, ensure_ascii=False, indent=2, default=str)

# Print summary
print(f"PID: {r['patent_id']}")
print(f"Title: {r['title'][:80]}")
print(f"Filing: {r['filing_date']}, Pub: {r['publication_date']}")
print(f"Abstract: {len(r['abstract'])} chars")
print(f"Claim1: {len(r['claim1'])} chars")
print(f"Description: {len(r['description'])} chars")
print(f"Examples: {r['example_count']}")
print(f"Mol codes: {len(r['molecular_codes'])}")
print(f"Neg/Pos DA: {r['neg_da_count']}/{r['pos_da_count']} -> neg? {r['is_negative_da']}")
print(f"Elastic hits: {len(r['elastic_hits'])}")
print(f"Scattering hits: {len(r['scattering_hits'])}")
print(f"Params: {r['physical_params']}")
if r['error']:
    print(f"ERROR: {r['error']}")
print(f"Saved: {out_path}")

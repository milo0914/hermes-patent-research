#!/usr/bin/env python3
import sys, json, re, time
sys.stdout.reconfigure(line_buffering=True)
from playwright.sync_api import sync_playwright

url = sys.argv[1]
pid_expected = sys.argv[2]

result = {"url": url, "patent_id": pid_expected, "success": False}

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
        
        # Scroll to load full page
        for i in range(4):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(800)
        
        body = page.inner_text('body')
        
        # Title
        title = ''
        title_m = re.search(r'(.{10,150})\n\nAbstract', body)
        if title_m:
            title = title_m.group(1).strip()
        else:
            title_m2 = re.search(r'(.{10,150})\n.*?Inventors', body)
            if title_m2:
                title = title_m2.group(1).strip()
        
        # Abstract
        abstract = ''
        abs_m = re.search(r'Abstract\n([\s\S]{30,2000}?)\nClassifications', body)
        if abs_m:
            abstract = abs_m.group(1).strip()[:1000]
        
        # Claim 1 - multiple patterns
        claim1 = ''
        claim_patterns = [
            r'WHAT IS CLAIMED IS:\s*1\.\s+([\s\S]{20,3000}?)(?=\n2\.|Claims|\nDESCRIPTION)',
            r'CLAIMS\s*1\.\s+([\s\S]{20,3000}?)(?=\n2\.|Claims|\nDESCRIPTION)',
            r'1\.\s+A\s+([\s\S]{20,3000}?)(?=\n2\.|Claims)',
            r'1\.\s+([\s\S]{20,3000}?)(?=\n2\.|Claims)',
        ]
        for pat in claim_patterns:
            m = re.search(pat, body)
            if m:
                claim1 = m.group(1).strip().replace('\n', ' ')[:2000]
                break
        
        # If still no claim1, try JS evaluate on claim DOM elements
        if not claim1:
            try:
                claim_text = page.evaluate("""() => {
                    const claims = document.querySelectorAll('[class*="claim"]');
                    if (claims.length > 0) return claims[0].textContent.trim();
                    return '';
                }""")
                if claim_text and len(claim_text) > 20:
                    claim1 = claim_text[:2000]
            except:
                pass
        
        # Dates - from timeline events
        dates = {}
        try:
            events = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('.event.style-scope.application-timeline'))
                    .map(e => e.textContent.trim())
                    .filter(t => /filed|published|granted|priority/i.test(t));
            }""")
            for evt in events:
                dm = re.search(r'(\d{4}-\d{2}-\d{2})\s+(.*)', evt)
                if dm:
                    d, desc = dm.group(1), dm.group(2).lower()
                    if 'filed' in desc:
                        dates['filing_date'] = d
                    elif 'published' in desc or 'publication' in desc:
                        dates['publication_date'] = d
                    elif 'granted' in desc:
                        dates['grant_date'] = d
                    elif 'priority' in desc:
                        dates['priority_date'] = d
        except:
            pass
        
        # If no dates from JS, try regex
        if not dates:
            all_dates = re.findall(r'\d{4}-\d{2}-\d{2}', body)
            if len(all_dates) >= 2:
                dates['priority_date'] = all_dates[0]
                dates['filing_date'] = all_dates[1] if len(all_dates) > 1 else ''
                dates['publication_date'] = all_dates[-1] if len(all_dates) > 2 else ''
        
        # Description (for neg/pos DA counting and contrast mentions)
        desc = ''
        desc_m = re.search(r'Description\n([\s\S]{200,}?)\nClaims', body)
        if desc_m:
            desc = desc_m.group(1).strip()[:15000]
        else:
            # Fallback: take middle section
            desc = body[2000:17000] if len(body) > 17000 else body[2000:]
        
        # Neg/pos DA counting
        neg_count = len(re.findall(r'negative\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        pos_count = len(re.findall(r'positive\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        neg_delta = len(re.findall(r'\u0394\u03b5[^\w]*-[0-9]|delta\s*epsilon[^\w]*-[0-9]', desc, re.IGNORECASE))
        
        # Contrast mentions
        contrast_count = len(re.findall(r'contrast', desc, re.IGNORECASE))
        contrast_ratio_count = len(re.findall(r'contrast\s+ratio', desc, re.IGNORECASE))
        high_contrast_count = len(re.findall(r'high\s+contrast', desc, re.IGNORECASE))
        
        # Examples extraction
        examples = []
        example_matches = re.findall(r'(?:Example|EXAMPLE)\s*\d+[\.:].{0,300}', desc)
        if example_matches:
            examples = [m.strip()[:200] for m in example_matches[:10]]
        
        # Molecular structures - look for formula references
        mol_structs = []
        formula_matches = re.findall(r'(?:formula\s+(?:I|II|III|IV|V|1|2|3)[^\.;]{0,100})', desc, re.IGNORECASE)
        if formula_matches:
            mol_structs = list(set(formula_matches))[:10]
        
        # Physical parameters (delta-n, delta-epsilon, clearing point, etc.)
        phys_params = []
        # delta-epsilon values
        de_m = re.findall(r'\u0394\u03b5\s*=\s*[-+]?[0-9]+\.?[0-9]*', desc)
        phys_params.extend(de_m[:5])
        # delta-n values
        dn_m = re.findall(r'\u0394n\s*=\s*[0-9]+\.?[0-9]*', desc)
        phys_params.extend(dn_m[:5])
        # clearing point
        cp_m = re.findall(r'(?:clearing|T\(NI\))\s*(?:point|temp)?\s*[=:~]\s*[0-9]+\.?[0-9]*\s*\°?C?', desc, re.IGNORECASE)
        phys_params.extend(cp_m[:5])
        # contrast ratio values
        cr_m = re.findall(r'contrast\s+ratio\s*[=:~]\s*[0-9]+\.?[0-9]*', desc, re.IGNORECASE)
        phys_params.extend(cr_m[:5])
        
        # Determine if negative dielectric
        is_neg_da = False
        if neg_count > 0 and (neg_count >= pos_count or neg_delta > 0):
            is_neg_da = True
        elif pos_count > 0 and neg_count == 0:
            is_neg_da = False
        elif neg_count > 0 and pos_count > neg_count:
            is_neg_da = True  # mentions both but likely neg dominant
        else:
            is_neg_da = None  # unknown
        
        result.update({
            'success': True,
            'title': title,
            'abstract': abstract,
            'claim1': claim1,
            'claim1_length': len(claim1),
            'dates': dates,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'neg_delta_count': neg_delta,
            'is_negative_dielectric': is_neg_da,
            'contrast_count': contrast_count,
            'contrast_ratio_count': contrast_ratio_count,
            'high_contrast_count': high_contrast_count,
            'examples': examples,
            'example_count': len(examples),
            'molecular_structures': mol_structs,
            'phys_params': phys_params,
            'body_length': len(body)
        })
        
        browser.close()
        
except Exception as e:
    result['error'] = str(e)
    import traceback
    result['traceback'] = traceback.format_exc()

print(json.dumps(result, ensure_ascii=False))

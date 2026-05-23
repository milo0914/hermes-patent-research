#!/usr/bin/env python3
import sys, json, re, time
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
        
        for i in range(6):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(1000)
        
        # Title - try JS first
        title = ''
        try:
            title = page.evaluate("""() => {
                const h1 = document.querySelector('h1');
                if (h1) return h1.textContent.trim();
                const titleEl = document.querySelector('[itemprop="title"], .title, .invention-title');
                if (titleEl) return titleEl.textContent.trim();
                return '';
            }""")
        except:
            pass
        
        if not title:
            body = page.inner_text('body')
            # Title is usually the first big text after the patent number
            title_m = re.search(r'(?:US|WO|EP)\d+[A-Z]?\d?\s*[^\S\n]*\n\s*\n\s*([^\n]{10,200})', body)
            if title_m:
                title = title_m.group(1).strip()
            else:
                # Try heading
                title_m2 = re.search(r'(.{15,150})\n\nAbstract', body)
                if title_m2:
                    title = title_m2.group(1).strip()
        
        # Abstract via JS
        abstract = ''
        try:
            abstract = page.evaluate("""() => {
                const abs = document.querySelector('[itemprop="abstract"], .abstract, [class*="abstract"]');
                if (abs) return abs.textContent.trim().substring(0, 1500);
                return '';
            }""")
        except:
            pass
        
        if not abstract:
            body = page.inner_text('body')
            abs_m = re.search(r'Abstract\s*\n([\s\S]{30,2000}?)\n\s*(?:Classifications|Description|Images)', body, re.IGNORECASE)
            if abs_m:
                abstract = abs_m.group(1).strip()[:1500]
        
        # Claim 1 via JS
        claim1 = ''
        try:
            claim1 = page.evaluate("""() => {
                const claimSection = document.querySelector('[class*="claim"], [itemprop="claims"]');
                if (claimSection) {
                    const first = claimSection.querySelector('[num="1"], [class*="claim-1"], .claim:nth-child(1)');
                    if (first) return first.textContent.trim().substring(0, 3000);
                }
                // Fallback: get all claims text and extract first
                const claims = document.querySelectorAll('[class*="claim-text"]');
                if (claims.length > 0) return claims[0].textContent.trim().substring(0, 3000);
                return '';
            }""")
        except:
            pass
        
        if not claim1:
            body = page.inner_text('body')
            claim_patterns = [
                r'WHAT IS CLAIMED IS:\s*1\.\s+([\s\S]{20,3000}?)(?:\n\s*2\.|Claims\b|DESCRIPTION\b)',
                r'CLAIMS\s*1\.\s+([\s\S]{20,3000}?)(?:\n\s*2\.|Claims\b|DESCRIPTION\b)',
                r'1\.\s+(?:A|An|The)\s+([\s\S]{20,3000}?)(?:\n\s*2\.|Claims\b)',
            ]
            for pat in claim_patterns:
                m = re.search(pat, body)
                if m:
                    claim1 = m.group(1).strip().replace('\n', ' ')[:3000]
                    break
        
        # Full body text for detailed analysis
        body = page.inner_text('body')
        
        # Dates via JS timeline
        dates = {}
        try:
            events = page.evaluate("""() => {
                const els = document.querySelectorAll('.event.style-scope.application-timeline');
                if (els.length === 0) {
                    // Try broader selector
                    const all = document.querySelectorAll('[class*="timeline"] [class*="event"]');
                    return Array.from(all).map(e => e.textContent.trim());
                }
                return Array.from(els).map(e => e.textContent.trim());
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
        
        # Description section
        desc = ''
        desc_m = re.search(r'Description\s*\n([\s\S]{200,}?)\n\s*Claims\b', body, re.IGNORECASE)
        if desc_m:
            desc = desc_m.group(1).strip()[:25000]
        else:
            desc = body[3000:28000] if len(body) > 28000 else body[3000:]
        
        # Neg/pos DA counting in description
        neg_count = len(re.findall(r'negative\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        pos_count = len(re.findall(r'positive\s+dielectric\s+anisotropy', desc, re.IGNORECASE))
        
        # Contrast counting
        contrast_count = len(re.findall(r'contrast', desc, re.IGNORECASE))
        contrast_ratio_count = len(re.findall(r'contrast\s+ratio', desc, re.IGNORECASE))
        high_contrast_count = len(re.findall(r'high\s+contrast', desc, re.IGNORECASE))
        
        # Examples - improved extraction
        examples_raw = []
        # Pattern 1: "Example N" or "Working Example N" 
        ex_matches = re.findall(r'(?:Working\s+)?(?:Example|EXAMPLE)\s*(\d+)[.:]\s*(.{0,500}?)(?=(?:Working\s+)?(?:Example|EXAMPLE)\s*\d|[A-Z][a-z]+\s+(?:Table|Figure)|\n\n[A-Z]{2,})', desc, re.DOTALL)
        for num, text in ex_matches[:15]:
            examples_raw.append({"num": int(num), "text": text.strip()[:300]})
        
        # If no examples found, try alternative patterns
        if not examples_raw:
            ex_matches2 = re.findall(r'Example\s+(\d+).*?(?=Example\s+\d+|$)', desc, re.DOTALL)
            for i, (num, *rest) in enumerate(ex_matches2[:15]):
                examples_raw.append({"num": int(num) if num.isdigit() else i+1, "text": rest[0].strip()[:300] if rest else ''})
        
        # Molecular structures / formula references
        mol_refs = []
        # Chemical formula patterns
        formula_patterns = [
            r'formula\s+[(I|II|III|IV|V|VI|VII|VIII|IX|X)][^.;]{0,200}',
            r'of\s+formula\s+[IVX]+[^.;]{0,150}',
            r'compound\s+of\s+formula[^.;]{0,150}',
            r'general\s+formula[^.;]{0,150}',
        ]
        for pat in formula_patterns:
            matches = re.findall(pat, desc, re.IGNORECASE)
            mol_refs.extend(matches[:5])
        
        # Deduplicate molecular references
        seen_mol = set()
        mol_structs = []
        for m in mol_refs:
            if m not in seen_mol:
                seen_mol.add(m)
                mol_structs.append(m[:200])
        
        # Physical parameter values in examples
        phys_data = []
        # delta-epsilon values
        de_vals = re.findall(r'[Δd][eε]\s*[=≈~]\s*[-+]?[\d.]+', desc)
        phys_data.extend(de_vals[:8])
        # delta-n values  
        dn_vals = re.findall(r'Δn\s*[=≈~]\s*[\d.]+', desc)
        phys_data.extend(dn_vals[:5])
        # Clearing point / T(NI)
        cp_vals = re.findall(r'(?:clearing\s+point|T\(N,I?\))\s*[=≈~:]\s*[\d.]+\s*°?C?', desc, re.IGNORECASE)
        phys_data.extend(cp_vals[:5])
        # Contrast ratio values
        cr_vals = re.findall(r'contrast\s*(?:ratio)?\s*[=≈~:]\s*[\d.]+', desc, re.IGNORECASE)
        phys_data.extend(cr_vals[:5])
        # VHR (voltage holding ratio)
        vhr_vals = re.findall(r'VHR\s*[=≈~:]\s*[\d.]+', desc)
        phys_data.extend(vhr_vals[:5])
        
        # Is negative dielectric?
        is_neg_da = None
        if neg_count > 0 and (neg_count >= pos_count):
            is_neg_da = True
        elif pos_count > 0 and neg_count == 0:
            is_neg_da = False
        elif neg_count > 0:
            is_neg_da = True  # mentions both but likely mixed
        
        result.update({
            'success': True,
            'title': title,
            'abstract': abstract[:1500],
            'claim1': claim1[:3000],
            'claim1_length': len(claim1),
            'dates': dates,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_dielectric': is_neg_da,
            'contrast_count': contrast_count,
            'contrast_ratio_count': contrast_ratio_count,
            'high_contrast_count': high_contrast_count,
            'examples': examples_raw,
            'example_count': len(examples_raw),
            'molecular_structures': mol_structs,
            'phys_data': phys_data,
            'body_length': len(body),
            'desc_length': len(desc)
        })
        
        browser.close()
        
except Exception as e:
    result['error'] = str(e)
    import traceback
    result['traceback'] = traceback.format_exc()

print(json.dumps(result, ensure_ascii=False))

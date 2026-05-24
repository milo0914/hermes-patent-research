#!/usr/bin/env python3
"""
Deep extract for 4 patents that need full data
"""
import json, re, time, sys, os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))

PIDS = ['US20240360362A1', 'US12305103B2', 'US12404452B2', 'US12163081B2']

def deep_extract(page, pid):
    """Full deep extraction of a patent page"""
    url = f"https://patents.google.com/patent/{pid}/en"
    print(f"  Deep extracting {pid}...")
    
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        # Get full inner_text (up to 200K chars for complete description)
        body_text = page.evaluate("""() => {
            return document.body.innerText.substring(0, 200000);
        }""") or ""
        
        # Title
        title = page.evaluate("""() => {
            const el = document.querySelector('invention-title');
            return el ? el.innerText.trim() : '';
        }""") or ""
        if not title:
            m = re.search(r'(.+?)\s*-\s*Google Patents', body_text[:200])
            if m: title = m.group(1).strip()
        
        # Abstract
        abstract = page.evaluate("""() => {
            const el = document.querySelector('div.abstract');
            return el ? el.innerText.trim() : '';
        }""") or ""
        
        # Claim 1
        claim1 = page.evaluate("""() => {
            const claims = document.querySelectorAll('div.claim, li.claim');
            if (claims.length > 0) return claims[0].innerText.trim();
            const ep_claims = document.querySelectorAll('ol.claims li.claim');
            if (ep_claims.length > 0) return ep_claims[0].innerText.trim();
            return '';
        }""") or ""
        
        # Claim 2
        claim2 = page.evaluate("""() => {
            const claims = document.querySelectorAll('div.claim, li.claim');
            if (claims.length > 1) return claims[1].innerText.trim();
            const ep_claims = document.querySelectorAll('ol.claims li.claim');
            if (ep_claims.length > 1) return ep_claims[1].innerText.trim();
            return '';
        }""") or ""
        
        # Description - extract from body text
        # Find "Description" section
        desc_start = body_text.find('Description')
        if desc_start == -1:
            desc_start = body_text.find('DETAILED DESCRIPTION')
        if desc_start == -1:
            desc_start = 0
        
        desc_end = body_text.find('Claims', desc_start + 100)
        if desc_end == -1:
            desc_end = len(body_text)
        
        description = body_text[desc_start:desc_end]
        
        # Dates
        dates = {}
        js_dates = page.evaluate("""() => {
            const result = {};
            document.querySelectorAll('time, [datetime]').forEach(el => {
                const dt = el.getAttribute('datetime') || el.innerText;
                if (dt && dt.match(/\\d{4}-\\d{2}-\\d{2}/)) {
                    const text = el.closest('div, span, li, td')?.innerText || '';
                    if (text.match(/filed|filing/i)) result.filed = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                    if (text.match(/priority/i)) result.priority = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                    if (text.match(/publish|publication/i)) result.published = dt.match(/\\d{4}-\\d{2}-\\d{2}/)[0];
                }
            });
            return result;
        }""") or {}
        dates.update(js_dates)
        
        # Regex fallback for dates
        if not dates.get('filed'):
            m = re.search(r'(?:Filing|Filed)\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', body_text, re.I)
            if m: dates['filed'] = m.group(1)
        if not dates.get('priority'):
            m = re.search(r'Priority\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', body_text, re.I)
            if m: dates['priority'] = m.group(1)
            else:
                all_d = re.findall(r'(\d{4}-\d{2}-\d{2})', body_text[:5000])
                if all_d: dates['priority'] = all_d[0]
        
        # Count neg/pos DA
        text_lower = body_text.lower()
        neg_patterns = [
            r'negative\s+dielectric\s+anisotropy',
            r'Δε\s*<\s*0',
            r'dielectric\s+anisotropy\s+Δε\s+is\s+negative',
            r'Δε\s+is\s+negative',
            r'negative\s+Δε',
        ]
        pos_patterns = [
            r'positive\s+dielectric\s+anisotropy',
            r'Δε\s*>\s*0',
            r'Δε\s+is\s+positive',
            r'positive\s+Δε',
        ]
        neg_count = sum(len(re.findall(p, text_lower)) for p in neg_patterns)
        pos_count = sum(len(re.findall(p, text_lower)) for p in pos_patterns)
        
        # Elastic hits with context
        elastic_patterns_ctx = {
            'elastic constant': r'elastic\s+constant.{0,120}',
            'K11': r'\bK11?\b.{0,80}',
            'K22': r'\bK22?\b.{0,80}',
            'K33': r'\bK33?\b.{0,80}',
            'splay elastic': r'splay\s+elastic.{0,100}',
            'twist elastic': r'twist\s+elastic.{0,100}',
            'bend elastic': r'bend\s+elastic.{0,100}',
        }
        elastic_hits = []
        for label, pat in elastic_patterns_ctx.items():
            for m in re.finditer(pat, text_lower):
                elastic_hits.append({label: m.group()[:150]})
        
        # Scattering hits with context
        scatter_patterns_ctx = {
            'scattering': r'scattering.{0,120}',
            'low scattering': r'low\s+scattering.{0,120}',
            'scatter': r'\bscatter\w*.{0,100}',
        }
        scattering_hits = []
        for label, pat in scatter_patterns_ctx.items():
            for m in re.finditer(pat, text_lower):
                scattering_hits.append({label: m.group()[:150]})
        
        # Physical parameters
        phys_params = []
        param_patterns = [
            (r'Δn\s*[=≈]\s*[\d.]+', 'Δn'),
            (r'Δε\s*[=≈]\s*[−-]?\s*[\d.]+', 'Δε'),
            (r'clearing\s+point.{0,30}\d+', 'clearing point'),
            (r'rotational\s+viscosity.{0,30}\d+', 'γ1'),
            (r'K(?:avg|1|2|3)\s*[=≈]\s*[\d.]+', 'K'),
        ]
        for pat, label in param_patterns:
            for m in re.finditer(pat, text_lower):
                phys_params.append({label: m.group()[:100]})
        
        # Example count
        example_count = len(re.findall(r'(?:Example|Exemplary\s+Embodiment)\s+\d+', body_text, re.I))
        
        # Molecular formula codes
        mol_codes = list(set(re.findall(r'\b[A-Z]{1,2}[-–]\d{1,4}[A-Z]?\b', body_text[:80000])))
        mol_codes = [c for c in mol_codes if len(c) <= 10 and not c.startswith('US-') and not c.startswith('EP-')]
        
        result = {
            'patent_id': pid,
            'url': f"https://patents.google.com/patent/{pid}/en",
            'title': title,
            'abstract': abstract[:3000],
            'claim1': claim1[:3000],
            'claim2': claim2[:1000],
            'description': description[:80000],
            'filing_date': dates.get('filed', ''),
            'priority_date': dates.get('priority', ''),
            'publication_date': dates.get('published', ''),
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_da': neg_count > pos_count,
            'elastic_hits': elastic_hits[:20],
            'scattering_hits': scattering_hits[:15],
            'physical_params': phys_params[:15],
            'example_count': example_count,
            'molecular_codes': mol_codes[:30],
            'body_length': len(body_text),
        }
        
        print(f"    title={title[:50]}")
        print(f"    dates={dates}")
        print(f"    neg={neg_count}, pos={pos_count}, elastic={len(elastic_hits)}, scatter={len(scattering_hits)}")
        print(f"    examples={example_count}, mol_codes={len(mol_codes)}, body_len={len(body_text)}")
        
        return result
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return {'patent_id': pid, 'error': str(e)}

def main():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        )
        page = ctx.new_page()
        
        for i, pid in enumerate(PIDS):
            print(f"\n[{i+1}/{len(PIDS)}] {pid}")
            result = deep_extract(page, pid)
            # Save individual extract
            out_path = f"{BASE}/extract_deep_{pid}.json"
            with open(out_path, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            results.append(result)
            time.sleep(3)
        
        browser.close()
    
    # Summary
    print("\n\n========================================")
    print("DEEP EXTRACTION SUMMARY")
    print("========================================")
    for r in results:
        pid = r.get('patent_id', '?')
        if 'error' in r:
            print(f"  {pid}: ERROR - {r['error'][:80]}")
        else:
            print(f"  {pid}: neg={r.get('neg_da_count',0)}, pos={r.get('pos_da_count',0)}, elastic={len(r.get('elastic_hits',[]))}, scatter={len(r.get('scattering_hits',[]))}, examples={r.get('example_count',0)}")

if __name__ == '__main__':
    main()

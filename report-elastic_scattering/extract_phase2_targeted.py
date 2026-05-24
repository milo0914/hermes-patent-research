#!/usr/bin/env python3
"""
Phase 2 Extract: Extract and assess new patents for negative DA + elastic/scattering
Processes US patents first, then EP
"""
import json, re, time, sys, os, subprocess
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))

# Priority list - US A1 first (most likely 2020+), then B2
PRIORITY_PIDS = [
    'US20240067879A1', 'US20240376382A1', 'US20240360362A1', 'US20230383186A1',
    'US20230323207A1', 'US20230357637A1', 'US20230295511A1', 'US20230295510A1',
    'US20230272282A1', 'US20220119711A1',
    'US12404452B2', 'US12325817B2', 'US12305103B2', 'US12264276B2',
    'US12258510B2', 'US12163081B2', 'US12104109B2', 'US11952527B2', 'US11802243B2',
]

# Already known neg DA PIDs
KNOWN_NEG = {'US20250101305A1', 'US20250189829A1', 'US20250215323A1', 'US20250284151A1', 'EP4680691A1', 'EP4400561A1'}

def extract_patent(page, pid):
    """Extract patent details from Google Patents page"""
    url = f"https://patents.google.com/patent/{pid}/en"
    print(f"  Extracting {pid}...")
    
    try:
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(3)
        
        # Get full page text
        body_text = page.evaluate("() => document.body.innerText") or ""
        
        # Get title
        title = page.evaluate("""() => {
            const el = document.querySelector('invention-title');
            return el ? el.innerText : '';
        }""") or ""
        
        # Get abstract
        abstract = page.evaluate("""() => {
            const el = document.querySelector('div.abstract');
            return el ? el.innerText : '';
        }""") or ""
        
        # Get claim 1
        claim1 = page.evaluate("""() => {
            const claims = document.querySelectorAll('div.claim, li.claim');
            if (claims.length > 0) return claims[0].innerText;
            // EP patent: ol.claims > li.claim
            const ep_claims = document.querySelectorAll('ol.claims li.claim');
            if (ep_claims.length > 0) return ep_claims[0].innerText;
            return '';
        }""") or ""
        
        # Get dates from timeline
        dates = page.evaluate("""() => {
            const result = {};
            const timeline = document.querySelectorAll('timeline-item, [data-proto="timeline-item"]');
            timeline.forEach(item => {
                const text = item.innerText || '';
                const dateMatch = text.match(/(\\d{4}-\\d{2}-\\d{2})/);
                if (dateMatch) {
                    if (text.includes('Filed') || text.includes('Filing')) result.filed = dateMatch[1];
                    if (text.includes('Priority')) result.priority = dateMatch[1];
                    if (text.includes('Published') || text.includes('Publication')) result.published = dateMatch[1];
                    if (text.includes('Grant')) result.granted = dateMatch[1];
                }
            });
            return result;
        }""") or {}
        
        # Also try to extract dates from the page text
        if not dates.get('filed'):
            filed_match = re.search(r'Filed[:\s]+(\d{4}-\d{2}-\d{2})', body_text)
            if filed_match:
                dates['filed'] = filed_match.group(1)
        if not dates.get('priority'):
            pri_match = re.search(r'Priority[:\s]+(\d{4}-\d{2}-\d{2})', body_text)
            if pri_match:
                dates['priority'] = pri_match.group(1)
        
        # Count negative and positive DA mentions in first 80K chars
        text_lower = body_text[:80000].lower()
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
        
        # Check for elastic constant mentions
        elastic_patterns = [
            r'elastic\s+constant',
            r'\bK11\b', r'\bK22\b', r'\bK33\b',
            r'\bK1\b', r'\bK2\b', r'\bK3\b',
            r'splay\s+elastic',
            r'twist\s+elastic',
            r'bend\s+elastic',
            r'elastic\s+modulus',
        ]
        elastic_count = sum(len(re.findall(p, text_lower)) for p in elastic_patterns)
        has_elastic = elastic_count > 0
        
        # Check for scattering mentions
        scatter_patterns = [
            r'scattering',
            r'light\s+scattering',
            r'forward\s+scattering',
            r'backward\s+scattering',
            r'scatter\s+angle',
            r'reduce\s+scattering',
            r'low\s+scattering',
        ]
        scatter_count = sum(len(re.findall(p, text_lower)) for p in scatter_patterns)
        has_scattering = scatter_count > 0
        
        # Determine negative DA status
        is_negative_da = neg_count > pos_count and neg_count >= 2
        
        # Check filing date range (2020-2026)
        filed_str = dates.get('filed', dates.get('priority', ''))
        in_range = False
        if filed_str:
            try:
                filed_year = int(filed_str[:4])
                in_range = 2020 <= filed_year <= 2026
            except:
                pass
        
        result = {
            'patent_id': pid,
            'title': title[:200],
            'abstract': abstract[:2000],
            'claim1': claim1[:2000],
            'dates': dates,
            'neg_da_count': neg_count,
            'pos_da_count': pos_count,
            'is_negative_da': is_negative_da,
            'elastic_count': elastic_count,
            'has_elastic': has_elastic,
            'scatter_count': scatter_count,
            'has_scattering': has_scattering,
            'in_date_range': in_range,
            'body_length': len(body_text),
        }
        
        print(f"    title={title[:50]}, neg={neg_count}, pos={pos_count}, "
              f"elastic={elastic_count}, scatter={scatter_count}, "
              f"negDA={is_negative_da}, filed={filed_str}, inRange={in_range}")
        
        return result
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return {'patent_id': pid, 'error': str(e)}

def main():
    results = []
    confirmed_neg_new = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        )
        page = ctx.new_page()
        
        for i, pid in enumerate(PRIORITY_PIDS):
            print(f"\n[{i+1}/{len(PRIORITY_PIDS)}] {pid}")
            result = extract_patent(page, pid)
            results.append(result)
            
            # Track confirmed neg DA in range
            if (result.get('is_negative_da') and 
                result.get('in_date_range') and
                pid not in KNOWN_NEG):
                confirmed_neg_new.append(pid)
                print(f"    >>> NEW CONFIRMED NEG DA: {pid}")
            
            time.sleep(2)
        
        browser.close()
    
    # Save all results
    out_path = f"{BASE}/extract_phase2_targeted.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n\n========================================")
    print("PHASE 2 EXTRACTION SUMMARY")
    print("========================================")
    
    neg_da_patents = [r for r in results if r.get('is_negative_da')]
    in_range_neg = [r for r in neg_da_patents if r.get('in_date_range')]
    
    print(f"Total extracted: {len(results)}")
    print(f"Negative DA confirmed: {len(neg_da_patents)}")
    print(f"Negative DA + in date range: {len(in_range_neg)}")
    
    print(f"\n--- Previously known neg DA: {len(KNOWN_NEG)} ---")
    for pid in sorted(KNOWN_NEG):
        print(f"  {pid}")
    
    print(f"\n--- NEW neg DA + in range ({len(in_range_neg)}): ---")
    for r in in_range_neg:
        elastic_str = f"K11/K22/K33={r.get('elastic_count',0)}" if r.get('has_elastic') else "no elastic"
        scatter_str = f"scatter={r.get('scatter_count',0)}" if r.get('has_scattering') else "no scatter"
        filed = r.get('dates', {}).get('filed', r.get('dates', {}).get('priority', '?'))
        print(f"  {r['patent_id']}: filed={filed}, neg={r['neg_da_count']}, pos={r['pos_da_count']}, {elastic_str}, {scatter_str}")
    
    print(f"\n--- Not neg DA or out of range ---")
    for r in results:
        if not r.get('is_negative_da') or not r.get('in_date_range'):
            reason = "pos DA" if r.get('pos_da_count',0) > r.get('neg_da_count',0) else "out of range" if not r.get('in_date_range') else "ambiguous"
            print(f"  {r['patent_id']}: {reason} (neg={r.get('neg_da_count',0)}, pos={r.get('pos_da_count',0)}, filed={r.get('dates',{})})")
    
    # Calculate total
    total_neg = len(KNOWN_NEG) + len(in_range_neg)
    print(f"\nTOTAL NEG DA PATENTS: {len(KNOWN_NEG)} (known) + {len(in_range_neg)} (new) = {total_neg}")
    print(f"Target: 10, Still need: {max(0, 10 - total_neg)}")
    
    return results

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Phase 2 Targeted Search: Better PID extraction with more scrolling
+ New query combinations to find more negative DA patents
"""
import json, re, time, sys, os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
KNOWN_PIDS = set()

def load_known():
    """Load all PIDs we already know about"""
    import glob
    for f in glob.glob(f"{BASE}/search_*.json") + glob.glob(f"{BASE}/extract_*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for k,v in data.items():
                    if k == 'patent_ids' and isinstance(v, list):
                        KNOWN_PIDS.update(v)
                    elif isinstance(v, str) and re.match(r'^[A-Z]{2}\d+[A-Z]\d?$', v):
                        KNOWN_PIDS.add(v)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        pid = item.get('patent_id', item.get('pid', ''))
                        if pid:
                            KNOWN_PIDS.add(pid)
        except:
            pass

def extract_pids_with_scroll(page, url, max_scrolls=15):
    """Navigate to search results, scroll aggressively, extract all PIDs"""
    print(f"  Navigating: {url[:100]}...")
    page.goto(url, wait_until='networkidle', timeout=60000)
    time.sleep(3)
    
    # Scroll multiple times to load all results
    for i in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)
        # Check if we've loaded everything
        count = page.evaluate("""() => {
            const items = document.querySelectorAll('search-result-item');
            return items.length;
        }""")
        if i > 5 and count == page.evaluate("""() => {
            const items = document.querySelectorAll('search-result-item');
            return items.length;
        }"""):
            break
    
    # Extract all PIDs from the page using inner_text
    body_text = page.evaluate("""() => {
        return document.body.innerText;
    }""")
    
    # Also try to get PIDs from search-result-item elements
    pids_from_dom = page.evaluate("""() => {
        const items = document.querySelectorAll('search-result-item');
        const pids = [];
        items.forEach(item => {
            const href = item.getAttribute('href') || '';
            const match = href.match(/patent\\/([A-Z]{2}\\d+[A-Z]\\d?)/);
            if (match) pids.push(match[1]);
            // Also check inner text
            const text = item.innerText || '';
            const tmatch = text.match(/^([A-Z]{2}\\d+[A-Z]\\d?)/m);
            if (tmatch) pids.push(tmatch[1]);
        });
        return [...new Set(pids)];
    }""")
    
    # Extract PIDs from full page text using regex
    pid_pattern = re.compile(r'\b([A-Z]{2}\d{4,}[A-Z]\d?(?:A1|B2|A2|B1)?)\b')
    pids_from_text = pid_pattern.findall(body_text)
    
    all_pids = list(set(pids_from_dom + pids_from_text))
    # Filter for real patent IDs (not random text)
    valid_pids = [p for p in all_pids if re.match(r'^(US|EP|WO)\d{6,}[A-Z]\d?$', p)]
    
    # Also get result count
    result_count = page.evaluate("""() => {
        const el = document.querySelector('.result-count, [data-proto="result-count"]');
        if (el) return parseInt(el.innerText) || 0;
        const match = document.body.innerText.match(/(\\d+)\\s*results?/i);
        return match ? parseInt(match[1]) : 0;
    }""")
    
    print(f"  DOM PIDs: {len(pids_from_dom)}, Text PIDs: {len(valid_pids)}, Result count: {result_count}")
    return valid_pids, result_count, len(body_text)

def run_searches():
    load_known()
    print(f"Known PIDs before search: {sorted(KNOWN_PIDS)}")
    print(f"Count: {len(KNOWN_PIDS)}")
    
    # New targeted queries - focus on finding NEGATIVE DA patents with elastic/scattering
    # Using assignee variants + negative DA + specific terms
    queries = [
        # Format: (label, assignee, query_text, after_priority)
        ("N1", "Merck Patent GmbH", '"negative dielectric anisotropy" "K33" OR "K11" OR "K22"', "20200101"),
        ("N2", "Merck Patent GmbH", '"negative dielectric" "elastic constant" "medium"', "20200101"),
        ("N3", "Merck KGaA", '"Δε" "negative" "liquid crystal medium"', "20200101"),
        ("N4", "Merck Electronics KGaA", '"negative dielectric anisotropy" "elastic" "liquid crystal"', "20200101"),
        ("N5", "Merck Patent GmbH", '"negative Δε" "medium"', "20200101"),
        ("N6", "Merck Patent GmbH", '"Δε<0" OR "Δε <0" OR "Δε is negative" "liquid crystal"', "20200101"),
        ("N7", "Merck Patent GmbH", '"vertical alignment" "K33" OR "elastic constant" "medium"', "20200101"),
        ("N8", "Merck Patent GmbH", '"VA mode" "negative" "liquid crystal medium"', "20200101"),
        # Try without date filter for broader reach
        ("N9", "Merck Patent GmbH", '"negative dielectric anisotropy" "elastic" "liquid crystal medium"', "20200101"),
        ("N10", "Merck Patent GmbH", '"negative dielectric anisotropy" "scattering" "liquid crystal"', "20200101"),
        # CPC code G02F1/137 (LC devices with negative DA)  
        ("N11", "Merck Patent GmbH", '"liquid crystal" "medium" (G02F1/137)', "20200101"),
        # Different approach: search for LC medium with specific compound classes that are neg DA
        ("N12", "Merck Patent GmbH", '"liquid crystal medium" "formula I" "formula II" "negative" "Δε"', "20200101"),
    ]
    
    all_results = {}
    new_pids_all = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        )
        page = ctx.new_page()
        
        for label, assignee, q, after_date in queries:
            # Build URL
            enc_q = q.replace(' ', '+').replace('"', '%22').replace('(', '%28').replace(')', '%29').replace('OR', '%7COR%7C')
            enc_assignee = assignee.replace(' ', '+')
            url = f"https://patents.google.com/?assignee={enc_assignee}&q={enc_q}&after=priority:{after_date}"
            
            try:
                pids, result_count, body_len = extract_pids_with_scroll(page, url, max_scrolls=12)
                new_pids = [pid for pid in pids if pid not in KNOWN_PIDS]
                
                all_results[label] = {
                    'url': url,
                    'patent_ids': pids,
                    'new_pids': new_pids,
                    'results_count': result_count,
                    'body_length': body_len
                }
                
                new_pids_all.update(new_pids)
                print(f"  [{label}] total={len(pids)}, new={len(new_pids)}: {new_pids[:5]}")
                
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")
                all_results[label] = {'url': url, 'error': str(e)}
            
            time.sleep(2)
        
        # If we still have few new PIDs, try a completely different approach:
        # Navigate to individual patent pages that cite our known neg DA patents
        # This finds "similar" or "cited by" patents
        print("\n\n=== CITATION SEARCH ===")
        known_neg = ['US20250101305A1', 'US20250189829A1', 'US20250215323A1', 'US20250284151A1', 'EP4680691A1', 'EP4400561A1']
        
        for ref_pid in known_neg[:3]:  # Check top 3
            try:
                cite_url = f"https://patents.google.com/patent/{ref_pid}/en"
                page.goto(cite_url, wait_until='networkidle', timeout=60000)
                time.sleep(3)
                
                # Look for "Similar documents" or "Cited by" section
                body_text = page.evaluate("() => document.body.innerText")
                
                # Find "Similar documents" section
                similar_match = re.search(r'Similar documents?\s*\n([\s\S]{0,3000})(?:\n\n|\n[A-Z])', body_text)
                if similar_match:
                    similar_text = similar_match.group(1)
                    similar_pids = pid_pattern.findall(similar_text)
                    valid_similar = [p for p in similar_pids if re.match(r'^(US|EP|WO)\d{6,}[A-Z]\d?$', p)]
                    new_similar = [p for p in valid_similar if p not in KNOWN_PIDS and p != ref_pid]
                    print(f"  [{ref_pid}] Similar docs: {len(valid_similar)} found, {len(new_similar)} new: {new_similar[:5]}")
                    all_results[f"similar_{ref_pid}"] = {
                        'similar_pids': valid_similar,
                        'new_similar': new_similar
                    }
                    new_pids_all.update(new_similar)
                
                # Find "Cited by" section  
                cited_match = re.search(r'Cited by\s*\n([\s\S]{0,3000})(?:\n\n|\n[A-Z])', body_text)
                if cited_match:
                    cited_text = cited_match.group(1)
                    cited_pids = pid_pattern.findall(cited_text)
                    valid_cited = [p for p in cited_pids if re.match(r'^(US|EP|WO)\d{6,}[A-Z]\d?$', p)]
                    new_cited = [p for p in valid_cited if p not in KNOWN_PIDS and p != ref_pid]
                    print(f"  [{ref_pid}] Cited by: {len(valid_cited)} found, {len(new_cited)} new: {new_cited[:5]}")
                    all_results[f"cited_{ref_pid}"] = {
                        'cited_pids': valid_cited,
                        'new_cited': new_cited
                    }
                    new_pids_all.update(new_cited)
                
            except Exception as e:
                print(f"  [{ref_pid}] citation search ERROR: {e}")
            
            time.sleep(2)
        
        browser.close()
    
    # Save results
    out_path = f"{BASE}/search_phase2_targeted.json"
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n\n=== SUMMARY ===")
    print(f"Total new PIDs found: {len(new_pids_all)}")
    print(f"New PIDs: {sorted(new_pids_all)}")
    print(f"Results saved to: {out_path}")
    
    return all_results, new_pids_all

if __name__ == '__main__':
    pid_pattern = re.compile(r'\b([A-Z]{2}\d{4,}[A-Z]\d?(?:A1|B2|A2|B1)?)\b')
    run_searches()

#!/usr/bin/env python3
"""Batch extract patent details - contrast focused, US patents batch 2 (remaining 4)"""
import sys, json, re, time, subprocess
sys.stdout.reconfigure(line_buffering=True)

SEARCH_FILE = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_search_results.json'
OUTPUT_FILE = '/data/.hermes/skills/research/patent-playwright-scraper/reports/contrast_extract_batch2.json'
EXTRACT_SCRIPT = '/data/.hermes/skills/research/patent-playwright-scraper/reports/extract_single_patent.py'

with open(SEARCH_FILE) as f:
    search_data = json.load(f)

us_patents = [p for p in search_data['patent_ids'] if p.startswith('US')]
remaining = us_patents[9:]  # Skip first 9 (already extracted)

print(f"Remaining US patents: {len(remaining)}")
for p in remaining:
    print(f"  {p}")

urls = [f"https://patents.google.com/patent/{pid}/en" for pid in remaining]

all_results = []
for i, (url, pid) in enumerate(zip(urls, remaining)):
    print(f"\n[{i+1}/{len(urls)}] Extracting {pid}...")
    try:
        proc = subprocess.run(
            ['python3', '-u', EXTRACT_SCRIPT, url, pid],
            capture_output=True, text=True, timeout=90
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        all_results.append(data)
                        print(f"  OK - claim1: {data.get('claim1_length',0)} chars")
                        print(f"  neg/pos: {data.get('neg_da_count',0)}/{data.get('pos_da_count',0)}")
                        print(f"  contrast: {data.get('contrast_count',0)} mentions")
                        print(f"  dates: {data.get('dates',{})}")
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                all_results.append({'patent_id': pid, 'success': False, 'error': 'No JSON output'})
        else:
            print(f"  Error: {proc.stderr[:200]}")
            all_results.append({'patent_id': pid, 'success': False, 'error': proc.stderr[:200]})
    except subprocess.TimeoutExpired:
        print(f"  Timeout")
        all_results.append({'patent_id': pid, 'success': False, 'error': 'Timeout'})
    time.sleep(1)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

ok_count = sum(1 for r in all_results if r.get('success'))
print(f"\nBatch 2 complete: {ok_count}/{len(all_results)} extracted successfully")

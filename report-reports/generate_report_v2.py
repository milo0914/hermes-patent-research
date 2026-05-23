#!/usr/bin/env python3
"""
生成 Merck 高對比 LCD 負介電液晶專利 Markdown 報告 v2
"""

import json, os, re
from datetime import datetime

REPORTS_DIR = os.path.dirname(os.path.abspath(__file__))

def load_data():
    fpath = os.path.join(REPORTS_DIR, 'contrast_final_list.json')
    with open(fpath) as f:
        data = json.load(f)
    return data['final_patents']

def format_claim1(claim1_text):
    """格式化 Claim 1，截斷過長內容"""
    if not claim1_text:
        return "（EP 專利 Claim 未完整提取，請參見原文）"
    text = claim1_text.strip()
    if len(text) > 800:
        return text[:800] + "..."
    return text

def format_contrast_snippets(snippets):
    """格式化 contrast 相關段落"""
    if not snippets:
        return "無 contrast 相關段落"
    result = []
    for i, s in enumerate(snippets[:5], 1):
        s = s.strip()
        if len(s) > 150:
            s = s[:150] + "..."
        result.append(f"  {i}. {s}")
    return "\n".join(result)

def format_mixture_examples(examples):
    """格式化混合實施例"""
    if not examples:
        return "無具體混合實施例數據"
    result = []
    for ex in examples[:5]:
        name = ex.get('name', '?')
        content = ex.get('content', '')[:200].strip()
        result.append(f"  **{name}**: {content}...")
    return "\n".join(result)

def format_phys_params(params):
    """格式化物理參數"""
    if not params:
        return "無物理參數"
    items = []
    labels = {
        'clearing_point': 'Cl.p.',
        'delta_n': 'Δn',
        'delta_epsilon': 'Δε',
        'epsilon_parallel': 'ε∥',
        'epsilon_perpendicular': 'ε⊥',
        'gamma1': 'γ1',
        'K1': 'K1',
        'K3': 'K3',
        'V0': 'V0',
        'VHR': 'VHR',
    }
    for key, val in params.items():
        label = labels.get(key, key)
        items.append(f"{label}={val}")
    return " | ".join(items)

def generate_report(patents):
    """生成完整 Markdown 報告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    lines = []
    lines.append("# Merck KGaA 高對比 LCD 負介電液晶材料專利調研報告")
    lines.append("")
    lines.append("**調研日期**: 2026-05-23")
    lines.append("**調研範圍**: Merck 集團（含 Merck Patent GmbH, Merck Electronics KGaA 等）")
    lines.append("**技術領域**: 改善 LCD 對比度（contrast）的負介電異向性（negative dielectric anisotropy）液晶材料")
    lines.append("**日期範圍**: Filing date 2024-01 ~ 2025-10")
    lines.append(f"**專利數量**: {len(patents)} 篇（去重後）")
    lines.append("**數據來源**: Google Patents (patents.google.com)")
    lines.append("")
    
    # 執行摘要
    lines.append("---")
    lines.append("")
    lines.append("## 執行摘要")
    lines.append("")
    lines.append("本報告系統性搜索並分析了 Merck 集團在 2024-2025 年間申請的、與 LCD 對比度改善相關的負介電液晶材料專利。")
    lines.append(f"共發現 **{len(patents)} 篇**符合條件的專利，涵蓋液晶介質組成物、反射式液晶面板、及含可聚合化合物的液晶介質等技術方向。")
    lines.append("")
    lines.append("**核心發現**:")
    lines.append("")
    
    # Key findings
    high_contrast = [p for p in patents if p.get('contrast_keyword_count', 0) >= 25]
    high_neg = [p for p in patents if p.get('negative_dielectric_count', 0) >= 50]
    with_phys = [p for p in patents if len(p.get('phys_params', {})) >= 5]
    
    lines.append(f"- **{len(high_contrast)} 篇**專利含豐富 contrast 相關描述（≥25 處提及）")
    lines.append(f"- **{len(high_neg)} 篇**專利深度涉及負介電異向性（≥50 處提及）")
    lines.append(f"- **{len(with_phys)} 篇**專利包含完整物理參數數據（Δε, Δn, Cl.p. 等）")
    lines.append("- 技術重點集中在：(1) 高對比度 VA/PSVA 模式液晶介質優化，(2) 降低驅動電壓同時維持高對比，(3) 改善 VHR 與回應時間的平衡")
    lines.append("- Merck 專利布局以 **Merck Patent GmbH** 和 **Merck Electronics KGaA** 為主要申請實體")
    lines.append("")
    
    # 專利清單總覽表
    lines.append("---")
    lines.append("")
    lines.append("## 專利清單總覽")
    lines.append("")
    lines.append("| # | 專利號 | 申請日期 | 標題 | negDA提及 | Contrast提及 | 物理參數 |")
    lines.append("|---|--------|----------|------|-----------|-------------|---------|")
    
    for i, p in enumerate(patents, 1):
        pid = p['patent_id']
        fd = p.get('dates', {}).get('filing_date', '') or p.get('dates', {}).get('priority_date', 'N/A')
        title = p.get('title', '')[:40]
        neg = p.get('negative_dielectric_count', 0)
        ctr = p.get('contrast_keyword_count', 0)
        phys_count = len(p.get('phys_params', {}))
        lines.append(f"| {i} | {pid} | {fd} | {title} | {neg} | {ctr} | {phys_count} |")
    
    lines.append("")
    
    # 逐篇詳細分析
    lines.append("---")
    lines.append("")
    lines.append("## 逐篇詳細分析")
    lines.append("")
    
    for i, p in enumerate(patents, 1):
        pid = p['patent_id']
        url = p.get('url', f'https://patents.google.com/patent/{pid}/en')
        dates = p.get('dates', {})
        fd = dates.get('filing_date', '') or dates.get('priority_date', 'N/A')
        pd = dates.get('priority_date', 'N/A')
        pubd = dates.get('publication_date', 'N/A')
        title = p.get('title', 'N/A')
        assignee = p.get('assignee', 'N/A')
        cpc = p.get('cpc_codes', [])
        abstract = p.get('abstract', '')
        claim1 = p.get('claim1', '')
        claim1_len = p.get('claim1_length', 0)
        neg = p.get('negative_dielectric_count', 0)
        pos = p.get('positive_dielectric_count', 0)
        is_neg = p.get('is_negative_dielectric', False)
        delta_eps = p.get('delta_eps_values', [])
        ctr_snippets = p.get('contrast_snippets', [])
        ctr_count = p.get('contrast_keyword_count', 0)
        mix = p.get('mixture_examples', [])
        phys = p.get('phys_params', {})
        mol = p.get('molecular_structures', [])
        
        lines.append(f"### {i}. {pid}")
        lines.append("")
        lines.append(f"- **專利號**: [{pid}]({url})")
        lines.append(f"- **標題**: {title}")
        lines.append(f"- **申請日期**: {fd}")
        lines.append(f"- **優先權日期**: {pd}")
        lines.append(f"- **公開日期**: {pubd}")
        lines.append(f"- **申請人**: {assignee}")
        lines.append(f"- **CPC 分類**: {', '.join(cpc) if cpc else 'N/A'}")
        lines.append("")
        
        # 摘要
        if abstract:
            abs_text = abstract[:500] + "..." if len(abstract) > 500 else abstract
            lines.append(f"**摘要**: {abs_text}")
            lines.append("")
        
        # 負介電確認
        neg_status = "✓ 確認負介電" if is_neg else "? 待確認"
        lines.append(f"**負介電確認**: {neg_status} (neg提及={neg}, pos提及={pos})")
        if delta_eps:
            lines.append(f"  - Δε 測量值: {', '.join(delta_eps[:3])}")
        lines.append("")
        
        # 技術特點
        lines.append("**技術特點（重點工作）**:")
        lines.append("")
        
        # Extract key technical points from contrast snippets
        tech_points = set()
        for s in ctr_snippets[:8]:
            s_lower = s.lower()
            if 'contrast ratio' in s_lower:
                tech_points.add("改善對比度（contrast ratio）")
            if 'high contrast' in s_lower:
                tech_points.add("高對比度顯示")
            if 'va mode' in s_lower or 'vertical alignment' in s_lower:
                tech_points.add("VA 垂直對齊模式")
            if 'psva' in s_lower or 'polymer stabilized' in s_lower:
                tech_points.add("PSVA 聚合物穩定垂直對齊")
            if 'response time' in s_lower:
                tech_points.add("改善回應時間")
            if 'voltage holding' in s_lower or 'vhr' in s_lower:
                tech_points.add("維持電壓保持率（VHR）")
            if 'transmittance' in s_lower:
                tech_points.add("提升透射率")
            if 'driving voltage' in s_lower or 'low voltage' in s_lower:
                tech_points.add("降低驅動電壓")
            if 'on-off' in s_lower:
                tech_points.add("on-off 對比度優化")
            if 'optical contrast' in s_lower:
                tech_points.add("光學對比度提升")
            if 'lateral fluorine' in s_lower or 'difluoro' in s_lower:
                tech_points.add("側向氟取代基設計（強化負介電）")
        
        if not tech_points:
            tech_points.add("液晶介質組成優化")
        
        for tp in sorted(tech_points):
            lines.append(f"- {tp}")
        lines.append("")
        
        # Claim 1
        lines.append("**Claim 1**:")
        lines.append("")
        lines.append(f"> {format_claim1(claim1)}")
        lines.append("")
        
        # 物理參數
        if phys:
            lines.append(f"**物理參數**: {format_phys_params(phys)}")
            lines.append("")
        
        # 分子結構代碼
        if mol:
            mol_str = ", ".join(mol[:20])
            lines.append(f"**分子結構代碼**: {mol_str}")
            lines.append("")
        
        # 混合實施例
        if mix:
            lines.append("**混合實施例**:")
            lines.append("")
            lines.append(format_mixture_examples(mix))
            lines.append("")
        
        # Contrast 相關段落
        if ctr_snippets:
            lines.append(f"**Contrast 相關段落**（共 {ctr_count} 處，展示前 5 處）:")
            lines.append("")
            lines.append(format_contrast_snippets(ctr_snippets))
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # 技術特點綜合分析
    lines.append("## 技術特點綜合分析")
    lines.append("")
    
    lines.append("### 1. 高對比度改善策略")
    lines.append("")
    lines.append("Merck 的專利技術主要通過以下策略改善 LCD 對比度：")
    lines.append("")
    lines.append("- **負介電異向性液晶介質優化**: 通過調整液晶分子的氟取代基數量和位置，增大 |Δε|，使液晶分子")
    lines.append("  在電場作用下更充分地垂直對齊，從而提升暗態遮光效果")
    lines.append("- **VA/PSVA 模式適配**: 大部分專利針對垂直對齊（VA）和聚合物穩定垂直對齊（PSVA）模式，")
    lines.append("  這兩種模式天然具有高對比度優勢")
    lines.append("- **驅動電壓降低**: 在維持高 |Δε| 的同時降低旋轉粘度 γ1，使 V0 降低，減少串擾導致的對比度劣化")
    lines.append("- **VHR 維持**: 高電壓保持率確保像素電壓穩定，避免漏電導致的對比度下降")
    lines.append("")
    
    lines.append("### 2. 分子結構設計趨勢")
    lines.append("")
    
    # Collect all molecular codes
    all_mols = set()
    for p in patents:
        for m in p.get('molecular_structures', []):
            all_mols.add(m)
    
    # Categorize
    core_neg = [m for m in all_mols if any(m.startswith(p) for p in ['CCY', 'CPY', 'PYP', 'CLY', 'CY'])]
    base_comp = [m for m in all_mols if any(m.startswith(p) for p in ['CC', 'CP', 'PP', 'CCC', 'CCV'])]
    pyrimidine = [m for m in all_mols if any(m.startswith(p) for p in ['PY', 'PGI', 'PGP', 'PGU'])]
    polymerizable = [m for m in all_mols if any(m.startswith(p) for p in ['RM', 'ST'])]
    
    lines.append(f"- **核心負介電化合物**: {', '.join(sorted(core_neg)[:15])}")
    lines.append(f"- **基礎組分**: {', '.join(sorted(base_comp)[:15])}")
    lines.append(f"- **嘧啶類**: {', '.join(sorted(pyrimidine)[:10])}")
    lines.append(f"- **可聚合化合物**: {', '.join(sorted(polymerizable)[:10])}")
    lines.append("")
    lines.append("設計趨勢：側向二氟取代（difluoro）的苯環或嘧啶環結構持續為核心負介電單元，")
    lines.append("搭配環己烷（cyclohexane）骨架提升化學穩定性，並引入乙烯基（vinyl）端基降低粘度。")
    lines.append("")
    
    lines.append("### 3. 物理參數範圍")
    lines.append("")
    
    # Collect phys param ranges
    clp_vals, dn_vals, deps_vals, gamma_vals = [], [], [], []
    for p in patents:
        phys = p.get('phys_params', {})
        if 'clearing_point' in phys:
            try: clp_vals.append(float(phys['clearing_point']))
            except: pass
        if 'delta_n' in phys:
            try: dn_vals.append(float(phys['delta_n']))
            except: pass
        if 'delta_epsilon' in phys:
            try: deps_vals.append(float(phys['delta_epsilon']))
            except: pass
        if 'gamma1' in phys:
            try: gamma_vals.append(float(phys['gamma1']))
            except: pass
    
    if clp_vals:
        lines.append(f"- **Clearing point (Cl.p.)**: {min(clp_vals):.1f} ~ {max(clp_vals):.1f} °C")
    if dn_vals:
        lines.append(f"- **Δn (589nm)**: {min(dn_vals):.3f} ~ {max(dn_vals):.3f}")
    if deps_vals:
        lines.append(f"- **|Δε| (1kHz)**: {min(deps_vals):.1f} ~ {max(deps_vals):.1f}")
    if gamma_vals:
        lines.append(f"- **γ1 (mPa·s)**: {min(gamma_vals):.1f} ~ {max(gamma_vals):.1f}")
    lines.append("")
    
    # 排除說明
    lines.append("---")
    lines.append("")
    lines.append("## 排除專利說明")
    lines.append("")
    lines.append("以下 2 篇專利因不符合條件被排除：")
    lines.append("")
    lines.append("| 專利號 | 原因 |")
    lines.append("|--------|------|")
    lines.append("| US20260015735A1 | 標題為 \"Formulation\"，無負介電提及（neg=0），無 contrast 提及（ctr=0），可能為藥物製劑專利誤入 |")
    lines.append("| EP4689796A1 | 標題為 \"Composition\"，無負介電提及（neg=0），數據不完整，可能是非液晶組成物 |")
    lines.append("")
    
    # 搜索策略說明
    lines.append("---")
    lines.append("")
    lines.append("## 搜索策略說明")
    lines.append("")
    lines.append("**關鍵字組合**（8 組搜索）：")
    lines.append("")
    lines.append("| 組別 | 申請人 | 關鍵字 | 命中數 |")
    lines.append("|------|--------|--------|--------|")
    lines.append('| S1 | Merck Patent GmbH | "contrast" + "liquid crystal" | 8 |')
    lines.append('| S2 | Merck Electronics KGaA | "contrast" + "liquid crystal" | 5 (新增) |')
    lines.append('| S3 | Merck Patent GmbH | "high contrast" + "liquid crystal" | 2 (新增) |')
    lines.append('| S4 | Merck Patent GmbH | contrast + "negative dielectric" | 2 (新增) |')
    lines.append('| S5 | Merck Patent GmbH | contrast + C09K19/30 | 2 (新增) |')
    lines.append('| S6 | Merck Patent GmbH | contrast + VA mode | 2 (新增) |')
    lines.append('| S7 | Merck KGaA | "contrast" + "liquid crystal" | 0 (新增) |')
    lines.append('| S8 | Merck Electronics KGaA | contrast + C09K19/30 | 0 (新增) |')
    lines.append("")
    lines.append("**日期過濾**: after=priority:20230101（確保 filing date 在 2024 年及之後）")
    lines.append("**排序**: sort=newest")
    lines.append("**去重**: 同一專利家族的 US A1/B2 版本取 Claim 1 最長者")
    lines.append("")
    
    # 免責聲明
    lines.append("---")
    lines.append("")
    lines.append("## 免責聲明")
    lines.append("")
    lines.append("本報告所有數據均來自 Google Patents 公開數據的自動提取，未經人工逐篇核實。")
    lines.append("Claim 1 內容可能因 Google Patents 頁面 DOM 結構差異而不完整（特別是 EP 專利）。")
    lines.append("物理參數和分子結構代碼為自動解析結果，建議重要用途前參見專利原文。")
    lines.append(f"報告生成時間: {now}")
    lines.append("")
    
    return "\n".join(lines)


def main():
    patents = load_data()
    report = generate_report(patents)
    
    out_path = os.path.join(REPORTS_DIR, 'merck_lcd_contrast_patents_v2.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"報告已生成: {out_path}")
    print(f"字數: {len(report):,}")
    print(f"專利數: {len(patents)}")
    return out_path


if __name__ == '__main__':
    main()

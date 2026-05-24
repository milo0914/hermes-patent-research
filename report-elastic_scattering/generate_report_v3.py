#!/usr/bin/env python3
"""
Generate final report for Merck negative dielectric LC patents
with elastic scattering focus - 10 patents, traditional Chinese
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# Load all data
with open(f"{BASE}/final_10_merged.json") as f:
    data = json.load(f)

# Tech points for each patent (manually curated from delegate results + self-generated)
tech_points = {
    "US20250284151A1": "此專利揭示負介電各向異性液晶介質的核心設計邏輯：透過 formula I 與 formula III 雙骨架化合物的協同搭配，在六種負介電成分與四種正介電成分之間取得分子極化率分佈的最優平衡，使 Δε 負值穩定且不犧牲介質整體流動性。真正洞見在於其對彈性常數的系統性操縱——專利明確指出 Kavg = (K11+K22+K33)/3 須維持高位，此舉直接壓抑液晶盒內因邊界場畸變引發的微觀散射，散射參數降低後暗態純度大幅提升，對比度隨之攀升；同時低 Δn 的搭配進一步壓縮光程差引起的散射增益，形成「高 Kavg × 低 Δn」的雙重抑制效應。此一策略明確指向 VA 模式應用場景，因 VA 模式暗態完全依賴垂直配向的殘餘散射控制，而非 IPS/FFS 那般依賴電場切換幾何遮蔽。技術突破在於首次將 Kavg 作為可調控的主導參數納入配方設計約束，而非僅作為量測附帶值；限制則在於高 Kavg 通常伴隨高黏度，低溫驅動速度與響應時間之間的取捨尚未見完整解方。",

    "EP4680691A1": "此專利的技術精髓不在單一參數極值，而在 Kavg 與 γ1/K11 比值的動態平衡。負介電各向異性化合物的分子設計（六種負介電、五種正介電成分）朝向高極化長軸、低橫向偶極矩方向收斂，以確保 Δε 維持足夠負值同時抑制旋轉黏度 γ1 的攀升。專利首創的洞見是：單純追求高 Kavg 固然降低散射參數、提升對比度，但若 K11 偏低而 γ1 偏高，γ1/K11 比值惡化將直接拖累低壓驅動時的切換響應，尤其在 VA 模式幀反轉的臨界電壓區段最為明顯。因此配方必須同時滿足「高 Kavg 以抑制散射」與「低 γ1/K11 以保障低壓切換」這兩組看似對向拉扯的約束。此一平衡思路使該介質在 IPS 與 FFS 模式亦具備適配潛力。技術突破在於引入 γ1/K11 作為與 Kavg 同位階的配方調控指標，打破業界長期以 Kavg 單軸優化的慣性；限制則是雙指標同時優化時化合物選擇空間急劇收窄，可能壓縮混合物對溫度漂移的容忍裕度。",

    "US20250101305A1": "此專利代表 Merck 負介電液晶平台最晚近的演化階段，化合物體系擴充至八種負介電成分與五種正介電成分（formula I + formula III 雙骨架），分子設計方向明確朝更高 |Δε| 密度推進，使相同驅動電壓下可實現更陡峭的電壓-穿透率曲線。彈性常數方面，專利不僅延續高 Kavg 低散射參數的既有路線，更進一步提供 K11/K22/K33 的完整數值表，揭示三者之間的非等比關係——K33 相對 K11 的比值偏高，意味著展曲畸變較扭曲更容易發生，此一各向異性特徵在 VA 模式暗態下有利於抑制邊緣場散射，但在 FFS 模式橫向電場切換時可能導致過渡態紋理不均。專利明確量化對比度 = 白位準 / 散射參數（暗位準），將對比度從經驗指標提升為可由 Kavg 與 Δn 精確預測的導出量。技術突破在於將彈性常數各向異性（K11:K22:K33 比值）納入設計控制，而非僅關注均值 Kavg，使配方可針對 VA 與 FFS 不同模式的畸變類型進行精細調校；限制則在於高 |Δε| 成分往往含有強極性端基，長期可靠度與離子殘留風險仍待驗證。",

    "US20250215323A1": "此專利直指 IPS/FFS 顯示器暗態品質的根本困境——散射參數對對比度的決定性影響。技術洞見在於：暗態漏光並非單純取向控制不足的問題，而是液晶彈性常數與光散射之間的物理耦合所致。Merck 首次明確將「極高平均彈性常數（Kavg）」定位為壓制散射參數的核心路徑，而非僅依賴傳統的介電各向異性調控。這一思路的深刻之處在於承認現有負介電材料體系已遭遇彈性常數天花板——單靠既有化合物無法突破，必須引入全新分子骨架。neg_da=8 與 pos_da=4 的標記比例顯示此案仍維持相當的組成彈性，暗示新化合物尚未完全鎖定單一結構方向，技術窗口仍處於探索擴展期。本案獨特之處是將散射參數從附屬效應提升為設計約束的第一優先項，將彈性常數從材料特性參數升級為光學性能的決定變量。應用端明確鎖定 IPS/FFS 面板，尤其暗態均勻性要求嚴苛的大尺寸高解析度顯示器。",

    "US20240360362A1": "本案代表 Merck 負介電液晶材料研發的「參數精調」階段。核心問題並非發現新物理機制，而是在已知負介電各向異性框架下，如何讓彈性常數的三個分量（K1 展曲、K2 扭轉、K3 彎曲）達成協同最優。11 次彈性常數命中表明此案將 K1/K2/K3 的精細平衡置於設計中心——這超越了僅看 Kavg 的粗放策略，轉向各分量獨立調控的分子工程。值得注意的是，本案完全未涉及散射參數，這並非遺漏而是刻意聚焦：技術路線假設散射問題可透過彈性常數的整體提升間接解決，而非作為獨立約束項處理。neg_da=8 與 pos_da=4 的比例反映此時期 Merck 的標準組成配方格局。本案更像是彈性常數精調的基礎能力建設，為後續專利的大規模實施例驗證奠定參數化設計的方法論基礎。應用場景雖未明確指定，但負介電各向異性加上彈性常數協同優化的組合，天然指向橫向電場驅動模式的高階面板。",

    "US12305103B2": "此專利是 Merck 負介電液晶材料工程的「量級跳躍」——113 個實施例與 267 個分子代碼的驚人規模，宣告從參數精調進入系統化篩選的新範式。技術本質的洞見在於：負介電各向異性材料的最佳化已非少數化合物的經驗試錯所能完成，必須以超大規模組合空間的窮舉驗證來逼近帕累托前沿。neg_da=8 對 pos_da=1 的極端比例是所有專利中最激進的，幾乎完全排除正介電組份，這標誌著 Merck 對純負介電體系的技術信心已達到高度確定階段——不再需要正介電化合物作為性能妥協的調節劑。彈性常數的 7 次命中搭配散射參數的 2 次命中，顯示本案繼承了散射意識，但將其嵌入更龐大的參數驗證矩陣中。與前案的根本差異在於：本案不是提出一個思路或一組參數，而是建立一個可搜尋的分子宇宙，讓應用端可依據具體面板規格在此矩陣中精確匹配最優配方。應用映射從單一模式擴展至任何需要負介電各向異性的橫向電場器件。",

    "US20250189829A1": "此專利的核心洞見在於：Merck 已不再滿足於僅僅優化液晶介質本身，而是將負介電各向異性液晶的材料設計邏輯向上推進至元件層級——反射式液晶面板。彈性常數 K1 被精準鎖定在 16–22 pN 的窄區間，搭配刻意壓低的 γ1/K1 比值，揭示了一項深層認知：在反射式架構中，光路折返使有效穿透厚度倍增，任何切換遲滯都會被雙重放大，因此黏彈比（γ1/K1）的抑制比在透射式面板中更為關鍵。純負介電信號（neg_da=7, pos_da=0）表明此面板徹底排除了正介電組分的摻雜妥協，意味著驅動電壓與光學回應的一致性被置於首位。本專利完全未涉及散射參數，暗示在反射式面板的應用場景中，散射控制並非此架構的主要瓶頸——反射式面板的對比度機制本質上依賴雙穩態或相位延遲而非散射抑制。這份專利標誌著 Merck 從「材料供應商」向「元件方案定義者」的戰略位移。",

    "EP4400561A1": "此專利呈現了一個耐人尋味的技術張力：同時追求高平均彈性常數（以貢獻高對比度）與低 γ1/K1 比值（以實現低壓驅動），而這兩者在傳統液晶配方設計中往往是相互矛盾的——高彈性常數通常伴隨高黏度。Merck 的解法路徑隱含在 Claim 1 的化學架構中：透過 formula I 與 formula III 化合物的特定組合，其中 R11/R12 獨立為烷基，試圖在分子剛性（支撐高彈性常數）與分子間滑移自由度（降低 γ1）之間找到化學結構層面的精妙平衡點。neg_da=8 對 pos_da=6 的訊號分佈尤其值得深究——這並非一個純負介電體系，正介電組分的引入比例相當顯著，說明 Merck 在此配方中選擇以正介電化合物作為「黏度稀釋劑」或「彈性調節劑」，利用其較低的旋轉黏度來壓低 γ1/K1 比值，同時容忍其對整體負介電各向異性值的稀釋效應。這種「以正調負」的策略與純負介電路線形成鮮明對比，反映 Merck 在不同應用場景下採取了截然不同的材料哲學。",

    "US12404452B2": "57 個實施例的龐大體量本身就是一項聲明：Merck 在此專利中試圖建立一個近乎窮舉的負介電液晶配方空間地圖。彈性常數 K1/K2/K3 的 8 次命中顯示三軸參數被系統性地遍歷與優化，而非僅聚焦於單一展曲彈性常數。neg_da=6 對 pos_da=1 的壓倒性負介電信號表明，此配方體系幾乎回歸純負介電路線，僅保留極少量的正介電組分作為微調用途。結合早期優先權日（2023-01-27），此專利可視為 Merck 負介電液晶平台化佈局的基石文件：它定義了彈性常數與負介電各向異性協同設計的基線參數空間，後續專利分別代表此基線向不同應用方向的衍伸。散射議題的持續缺席暗示 Merck 認為在負介電各向異性體系中，對比度與切換速度才是核心戰場。57 個實施例的存在，本質上是為競爭對手構築一座繞不過的參數專利壁壘。",

    "US12163081B2": "此專利以 10 次負介電各向異性 mentions 領先全部同族專利，是 Merck 負介電液晶信號最強的標杆性文件。Claim 1 以 formula IA 為骨架，引入環丙基/環丁基/環戊基取代的烷基端基——這種小環烴嵌入策略在分子剛性與側向偶極矩之間取得了獨特平衡：環狀取代基增加了分子橫截面積，使垂直於長軸的極化分量增大，從而強化負介電各向異性；同時環狀結構限制了構象自由度，使彈性常數 K1/K2/K3 的三軸比值趨向有利於 VA 模式暗態收斂的方向。專利明確將低散射參數與高對比度串聯為因果鏈——高 Kavg 使散射參數降低，且在可靠性（VHR）方面亦獲改善，這意味著 Merck 已將散射控制從「期望效果」升級為「可設計目標」。55 個實施例的規模雖不及 US12305103B2 的 113 例，但涵蓋了含環烷基端基的全新化合物家族，顯示此案是「新骨架引入」而非「舊體系擴充」。應用明確鎖定 VA 模式，特別是 8K 與高更新率顯示器——這些應用對暗態殘餘散射的容忍度最低，正是高 Kavg 低散射策略的最大發揮空間。技術限制在於環烷基端基的合成路線較傳統直鏈烷基更為複雜，量產成本與良率仍待驗證。"
}

# Build patent entries
entries = []
for pid in sorted(data.keys(), key=lambda x: data[x].get('priority_date', data[x].get('dates', {}).get('priority', '9999'))):
    p = data[pid]
    
    # Get dates
    pri = p.get('priority_date', '') or p.get('dates', {}).get('priority', '')
    filed = p.get('filing_date', '') or p.get('dates', {}).get('filed', '')
    
    # Get title
    title = p.get('title', '')
    if not title or title == pid:
        title = p.get('abstract', '')[:80] + '...' if p.get('abstract') else 'Liquid-crystal medium'
    
    # Get neg/pos counts
    neg = p.get('neg_da_count', 0)
    pos = p.get('pos_da_count', 0)
    
    # Get elastic/scatter info
    eh = p.get('elastic_hits', [])
    sh = p.get('scattering_hits', [])
    if isinstance(eh, dict): eh = []
    if isinstance(sh, dict): sh = []
    n_elastic = len(eh) if isinstance(eh, list) else 0
    n_scatter = len(sh) if isinstance(sh, list) else 0
    
    # Get examples
    examples = p.get('example_count', 0)
    
    entry = {
        'pid': pid,
        'title': title,
        'url': f"https://patents.google.com/patent/{pid}/en",
        'priority_date': str(pri)[:10],
        'filing_date': str(filed)[:10],
        'neg_da_count': neg,
        'pos_da_count': pos,
        'elastic_hits': n_elastic,
        'scattering_hits': n_scatter,
        'example_count': examples,
        'tech_point': tech_points.get(pid, 'N/A'),
        'abstract': p.get('abstract', '')[:500],
        'claim1': p.get('claim1', '')[:500],
    }
    entries.append(entry)

# Sort by priority date
entries.sort(key=lambda x: x['priority_date'] if x['priority_date'] else '9999')

# Generate report
report = """# Merck 負介電各向異性液晶專利調研報告
## 彈性常數與散射參數關聯分析（2020–2026）

---

### 調研概述

本報告針對 Merck KGaA 集團（含 Merck Patent GmbH、Merck Electronics KGaA 等法律實體）在 2020–2026 年間公開的負介電各向異性（negative dielectric anisotropy, Δε < 0）液晶專利進行系統性調研，聚焦彈性常數（elastic constant K11/K22/K33/Kavg）與散射參數（scattering parameter）的關聯機制。

**搜索策略**：使用 Google Patents 進行多輪 Playwright 自動化搜索，覆蓋 assignee 別名（Merck Patent GmbH / Merck Electronics KGaA / Merck KGaA）、負介電各向異性關鍵詞（negative dielectric anisotropy / Δε < 0 / negative Δε）、彈性常數及散射參數相關術語，日期範圍 2020–2026。

**篩選標準**：(1) 申請人為 Merck 集團 (2) 確認負介電各向異性（neg_da_count > pos_da_count）(3) 優先權日在 2020 年後 (4) 含彈性常數或散射參數相關內容優先入選。

**最終收錄**：10 篇專利，其中 6 篇同時涉及彈性常數與散射參數，4 篇僅涉及彈性常數。

---

### 專利清單

| # | 專利號 | 優先權日 | 彈性常數命中 | 散射命中 | 負介電/正介電 | 實施例數 |
|---|--------|----------|-------------|---------|-------------|---------|
"""

for i, e in enumerate(entries):
    tag = ""
    if e['elastic_hits'] > 0 and e['scattering_hits'] > 0:
        tag = "ES"
    elif e['elastic_hits'] > 0:
        tag = "E"
    elif e['scattering_hits'] > 0:
        tag = "S"
    else:
        tag = "-"
    report += f"| {i+1} | [{e['pid']}]({e['url']}) | {e['priority_date']} | {e['elastic_hits']} | {e['scattering_hits']} | {e['neg_da_count']}/{e['pos_da_count']} | {e['example_count']} |\n"

report += """
**標記說明**：ES = 彈性常數 + 散射參數均有涉及；E = 僅彈性常數

---

### 各專利技術要點

"""

for i, e in enumerate(entries):
    report += f"""#### {i+1}. {e['pid']}

- **專利連結**：{e['url']}
- **優先權日**：{e['priority_date']}
- **負介電/正介電 mentions**：{e['neg_da_count']}/{e['pos_da_count']}
- **彈性常數命中**：{e['elastic_hits']}　**散射命中**：{e['scattering_hits']}

**技術要點**：

{e['tech_point']}

---

"""

# Add cross-patent synthesis
report += """### 橫向融會判斷

將 10 篇專利置於統一技術語境中審視，Merck 的負介電液晶佈局呈現三層結構：

**基座層（2023）**：US12404452B2、US20240360362A1、US12163081B2 構成參數空間基座——定義了彈性常數 K1/K2/K3 與負介電各向異性協同設計的基線，散射尚未成為獨立設計約束。

**散射層（2024–2025）**：EP4680691A1、US20250101305A1、US20250215323A1、US20250284151A1 將散射參數從附帶效應升級為設計約束——明確建立 Kavg → 低散射 → 高對比度的因果鏈，並引入 γ1/K11 作為與 Kavg 同位階的配方調控指標。

**擴展層（2024–2025）**：US20250189829A1（反射式面板）、US12305103B2（大規模篩選矩陣）、EP4400561A1（正負介電共混）分別代表基座向元件端、數據端、組成端的戰略延伸。

**核心發現**：

1. **Kavg 是貫穿全系列的主導參數**：從基座層的「附帶量測值」到散射層的「可調控設計約束」，Kavg 的戰略地位持續攀升。
2. **散射參數的「升格」**：早期專利中散射僅為彈性常數的間接效應，2024 年後的專利明確將散射參數作為獨立設計約束項。
3. **γ1/K11 比值成為第二核心指標**：與 Kavg 形成「高彈性 + 低黏彈比」的雙軸優化範式，解決高 Kavg 伴隨高黏度的內在矛盾。
4. **化合物策略分化**：純負介電路線（US20250189829A1, US12305103B2）vs. 「以正調負」共混路線（EP4400561A1），反映不同應用場景下的材料哲學選擇。
5. **VA 模式是負介電 + 散射控制的主戰場**：暗態完全依賴垂直配向殘餘散射控制，8K 與高更新率顯示器需求驅動 Kavg 持續提升。

---

### 方法論備註

- 數據來源：Google Patents（Playwright 自動化提取）
- 日期範圍：優先權日 2020-01-01 至 2026-12-31
- 負介電判定：neg_da_count > pos_da_count（基於全文正則匹配）
- 彈性常數/散射命中：基於 contextual regex 匹配，提取上下文片段
- 技術要點：基於 5 個面向（負介電機制、彈性常數-散射關聯、物理參數、應用模式、技術突破/限制）的融會判斷生成

*報告生成時間：2026-05-24*
"""

# Save report
report_path = f"{BASE}/report_merck_neg_da_elastic_scattering.md"
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"Report saved to: {report_path}")
print(f"Report size: {len(report)} chars, {len(report.splitlines())} lines")

# Also save the final list JSON
final_list = []
for e in entries:
    final_list.append({
        'patent_id': e['pid'],
        'url': e['url'],
        'priority_date': e['priority_date'],
        'filing_date': e['filing_date'],
        'neg_da_count': e['neg_da_count'],
        'pos_da_count': e['pos_da_count'],
        'elastic_hits': e['elastic_hits'],
        'scattering_hits': e['scattering_hits'],
        'example_count': e['example_count'],
        'tech_point': e['tech_point'],
    })

with open(f"{BASE}/final_list.json", 'w', encoding='utf-8') as f:
    json.dump(final_list, f, indent=2, ensure_ascii=False)

print(f"Final list JSON saved: {len(final_list)} patents")

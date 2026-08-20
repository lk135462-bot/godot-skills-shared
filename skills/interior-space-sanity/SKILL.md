---
name: interior-space-sanity
description: AI 產圖室內設計空間合理性把關＋空間運用原則庫。任何 AI 生成室內／建築場景圖（等角剖面 isometric cutaway、平面圖 floor plan、宿舍／房間／基地剖面）的 prompt 撰寫前必讀（用空間運用原則設計格局、把約束寫進 prompt），產圖後驗收時必跑審圖檢查表。當使用者說「產室內圖」「等角剖面」「宿舍圖」「房間佈局圖」「floor plan」「格局怎麼配」「動線」「樓梯斷頭」「房間不連通」「門通往哪」「空間不合理」「審這張室內圖」時觸發。涵蓋：八大空間運用原則（動線／分區／視線／採光／垂直空間／收納／留白／彈性複合，各附 prompt 措辭）＋七大合理性檢核＋產後審圖表＋AI 空間錯誤圖鑑＋修正措辭。
---

# AI 產圖室內空間合理性（Interior Space Sanity）

## 角色定位

AI 影像模型（Midjourney／SDXL／GPT 產圖／Nano Banana…）**沒有 3D 世界模型**，畫室內圖時只憑「看起來像」的局部紋理拼貼，不懂空間拓撲。研究實證：即使 DALLE-3／MJ v6.1 級模型，平行線常收斂到多個不一致的消失點；AI 平面圖常見「樓梯撞牆」「浴室只能從臥室衣櫃進」等建築幻覺；樓梯佔地被系統性低估近半（實際一層約需 40 sq ft，AI 常只給 20–25）。

本 Skill 的職責：**產前先用空間運用原則把格局「設計」出來、把約束寫進 prompt；產後用檢查表逐項驗**——杜絕「畫得漂亮但住不了人」的圖。

## 引用時機（何時必讀本 Skill）

1. **產前**：任何 AI 生成室內／建築場景圖的 prompt 撰寫前 → 先用「§1 空間運用原則」把格局想清楚，再用「§2 產前檢查表」把約束寫進 prompt（含 §5 措辭範例）。
2. **產後**：圖生成出來後、交付／採用前 → 用「§3 產後審圖檢查表」逐項驗，任何一項不過就用 §5 修正措辭重生成。
3. **審圖**：使用者拿現成 AI 室內圖來問「哪裡不合理」→ 直接跑 §3＋對照 §4 圖鑑回報。

與 `video-prompt-engineer`（影片動態）、`sprite-prompt-engineer`（角色立繪）互補：**凡場景含室內格局，本 Skill 先過**。

---

## §1 空間運用原則（設計格局時的正面詞彙庫，每條附 prompt 落地措辭）

> 用法：寫 prompt 前先讀本節，挑出這張圖要用的 3–5 條原則，把「落地措辭」揉進 prompt 的格局宣告段（見 §5 結構化寫法）。原則不是全上——小空間重 ①⑤⑥⑧，展示型空間重 ③⑦。

### ① 動線設計（Circulation）
- **迴遊動線（circulation loop）**：讓主要區域之間有環狀路徑可繞一圈，不走回頭路、消滅死路；小宅用「中島／櫃體當環心」最常見。
- **廚房黃金三角（work triangle）**：冰箱—水槽—爐台三點成三角，三邊合計約 4–8m（13–26 ft）、單邊 1.2–2.7m；**主動線不得穿越三角**。
- **走道淨寬與人體尺度**：主走道 ≥90cm；廚房操作走道 ≥107cm（42in）、雙人共廚 ≥122cm（48in）；家具間留人能側身以上的空隙。
- **Prompt 措辭**：`a circulation loop connects the entrance, kitchen, living and sleeping areas with no dead-end corridors; kitchen with refrigerator, sink and stove arranged in a compact work triangle; all walkways at least 90cm wide`

### ② 機能分區（Zoning）
- **公共→半公共→私密的層次過渡**：玄關（緩衝）→ 客餐廚（公共）→ 走道（過渡）→ 寢區／更衣（私密）；訪客動線不穿越私區。
- **動靜分離**：吵的（健身、娛樂、廚房）與靜的（睡眠、閱讀）不直接相鄰，中間用衛浴／櫃體／走道當隔音緩衝帶。
- **乾濕分離**：淋浴／衛浴集中成濕區塊（管線邏輯），與更衣間相鄰成套；濕區有牆有門，絕不裸開在公共機能旁。
- **Prompt 措辭**：`public living and dining zone near the entrance, private sleeping zone at the far end, the noisy gym corner separated from the beds by the enclosed bathroom block, shower room and adjacent changing room grouped as one wet zone`

### ③ 視線軸線（Sightlines）
- **進門第一眼焦點**：開門的視線軸端要落在「端景」——特色牆、大窗、主家具；**不能是馬桶、雜物堆或一排謎之門**。
- **對景／框景**：門洞、開口如畫框，框住下一個空間的亮點；長軸線盡端放視覺焦點引導人走。
- **視覺穿透與遮擋**：需要分區又不想斷光時，用半高櫃、格柵、玻璃隔屏——擋視線的下半部、放行光線的上半部。
- **Prompt 措辭**：`the view from the entrance is framed toward a feature wall and large window at the end of the main axis; a half-height shelf partially screens the sleeping area without blocking light; doorways frame the room beyond like a picture`

### ④ 採光與開窗（Daylight）
- **自然光方向**：主要活動區（客餐廳、工作區）沿外牆配置吃日照；南向得光最久、東向給臥室晨光。
- **深處採光（borrowed light）**：平面深處用室內窗、玻璃隔間、高窗（clerestory）、天窗把光「借」進來，消滅暗房。
- **窗與機能對應**：書桌鄰窗、床避開頭頂直射、浴室用高窗兼顧採光與遮蔽；**窗一律開在外牆**，內牆開窗即失效。
- **Prompt 措辭**：`large windows along the living area exterior wall, bedroom window catching morning light, an interior glass partition borrows daylight into the inner hallway, a high clerestory window for the bathroom, no windows on interior walls`

### ⑤ 垂直空間利用（Vertical Space）
- **挑高**：公共聚集區給挑高（double-height）營造開闊；挑高區上方可對應夾層。
- **夾層（mezzanine／loft）**：睡眠或書房放上層省footprint；**必有樓梯＋樓板開口實際連通、上下淨高都要夠**（居住層 ≥2.0m）。
- **樓梯下空間**：做收納櫃、小工作桌、電器櫃或寵物窩——不留死角。
- **高櫃**：收納做到頂（full-height）比矮櫃省地又整齊。
- **Prompt 措辭**：`double-height living space, a sleeping loft above the bathroom block reached by the single staircase through a real floor opening, built-in storage drawers under the stairs, full-height wardrobe cabinets`

### ⑥ 收納規劃（Storage）
- **就近收納**：東西收在使用地點旁——玄關鞋櫃、床邊衣櫃、爐台邊吊櫃、健身角器材架；動線上「順手放得回去」才會整齊。
- **隱藏式收納**：櫃門與牆同色齊平、無把手，收納量大但視覺噪音低；髒亂機能（洗衣、雜物）藏進櫃牆或門後。
- **Prompt 措辭**：`a shoe cabinet beside the entrance door, wardrobes built flush into the bedroom wall with handleless fronts matching the wall color, kitchen wall cabinets above the counter, laundry hidden behind a cabinet door`

### ⑦ 家具比例與留白（Scale & Negative Space）
- **佔地率**：家具佔地面比例經驗值約 3–4 成，留 6 成以上空地；擁擠是毀掉空間尺度感最快的方式。
- **呼吸感（negative space）**：家具群組之間留大方的空白，每件主家具有自己的「氣場範圍」；留白本身是設計，不是沒做完。
- **比例尺**：以人（1.7m）、床（2m）、門（90×210cm）當隱形比例尺校對所有物件大小。
- **Prompt 措辭**：`furniture occupies only about one third of the floor area, generous open floor space between furniture groups, every object at realistic human scale (beds about 2m long, doors about 2.1m tall)`

### ⑧ 彈性／複合空間（Flexible Use）
- **一區多用**：餐桌兼工作桌、臥榻兼客床兼收納箱、掀床（murphy bed）收起變健身區。
- **可變隔間**：滑動拉門／摺疊門讓空間「平時開敞、需要時圍合」；比實牆多一種狀態。
- **時段分區**：同一區白天／夜晚不同用途時，家具要能收得走（可疊椅、摺疊桌）。
- **Prompt 措辭**：`a dining table that doubles as a shared work desk, a sliding partition that can open the bedroom to the living area, a fold-down wall bed freeing the floor for exercise`

---

## §2 產前 Prompt 檢查表（寫 prompt 前逐項確認，把約束寫進去）

| # | 檢核項 | 要求（源自室內設計基本原則） |
|---|--------|------------------------------|
| 1 | **動線連通** | 每個房間至少一個門／開口接到走道或相鄰公共區；圖中任兩點可以「不穿牆」走通；無死路（dead end） |
| 2 | **樓梯兩端落點** | 上端接樓板開口（上層地板要真的開洞）、下端落在空曠地面；**兩端各留一個 ≥90cm 深的淨空平台（landing）**，不被冰箱／櫃體／牆堵死；樓梯上方淨高留足（居住規範 ≥2.0m） |
| 3 | **門的去向** | 每扇門兩側都必須是「已定義的空間」；不畫成排的「通往未知」的門；門的開向不撞家具、不開在牆角；門開進平台時不得吃掉平台一半深度 |
| 4 | **乾濕分離** | 淋浴／衛浴自成一間、有門、有牆圍閉（濕區）；**更衣間緊鄰淋浴間**、經門進入，絕不裸開在健身區／公共機能旁；濕區集中配置（管線邏輯） |
| 5 | **機能分區（zoning）** | 公（玄關→客餐廚→公共活動）與私（寢區／更衣）動線分層：訪客不需穿越寢區；玄關進門先見過渡區（鞋櫃可以，但後方要接明確的廳或走道，不是一排謎之門） |
| 6 | **無孤島空間** | 任何被牆圍出的封閉區域都要有開口；**上下兩層必須有樓梯＋樓板開口實際連通**（不是兩個各自密封的盒子疊在一起）；不留不可進入的夾縫空間 |
| 7 | **家具不堵路** | 主要走道淨寬 ≥75–90cm；門扇迴轉範圍內無家具；大型家電（冰箱、機櫃）不放在動線端點與樓梯口；家具比例符合真人尺度 |
| 8 | **牆體幾何** | 牆線閉合成單純矩形／L 形，不交疊、不產生剩餘三角區或未知空腔；等角圖三軸各 120°、平行線保持平行、單一投影系統貫穿全圖 |

**執行方式**：先用文字把格局寫成一段「房間清單＋連通關係」（如：玄關—門—客廳—走道—寢區；樓梯連通上層平台），自己讀一遍能走通，再翻成 prompt。連通關係說不出口的格局，模型一定畫不對。

---

## §3 產後審圖檢查表（圖出來後逐項驗，全過才算合格）

核心方法：**小人測試（walk-through）**——想像一個小人從大門進入，實際「走」一遍。

- [ ] **W1 走遍全圖**：小人能否不穿牆到達圖中每一個房間／角落？走不到的區域＝孤島，Fail。
- [ ] **W2 樓梯追蹤**：手指沿樓梯走——下端落在哪？（要是空地＋平台，不是冰箱／牆／家具）上端接到哪？（上層地板要有對應開口）任一端斷頭即 Fail。
- [ ] **W3 逐門盤點**：每扇門打開後面是什麼？說不出來的門＝幽靈門，Fail。門的數量與房間數對得上嗎？
- [ ] **W4 濕區檢查**：淋浴／衛浴有沒有自己的一間（牆＋門）？更衣間是否鄰接淋浴、有門？更衣機能是否裸露在健身／公共區？
- [ ] **W5 上下層連通**：多層／上下鋪空間之間有沒有實際的樓梯＋開口？還是兩個獨立密封盒子？
- [ ] **W6 牆體幾何**：沿每道牆描一遍——有沒有交疊、斷裂、圍出「進不去的未知空間」？等角三軸是否一致（平行線仍平行）？
- [ ] **W7 家具佔位**：走道被家具掐斷了嗎？門／樓梯口前 90cm 內有無大型物件？家具與牆有無穿模重疊？
- [ ] **W8 尺度合理**：以床（約 2m）或門（約 90cm×210cm）當比例尺，其他物件尺寸合理嗎？樓梯級數×級深合計的水平投影夠長嗎（別被「三步登天」的迷你樓梯騙過）？
- [ ] **W9 空間品質**（加分項，對照 §1）：進門第一眼是端景還是雜物？窗開在外牆嗎？留白夠不夠（家具佔地 ≲4 成）？收納在使用點附近嗎？

**判定**：W1–W7 任一 Fail → 用 §5 措辭修正後重生成；只有 W8–W9 小瑕 → 可視用途放行並註記。

---

## §3.1 生活節點檢查（生活沙盒房間實戰教訓）

不要只檢查「能不能走到」，還要檢查「生活動作是否成組」。審圖時逐一找出入口、睡眠、工作、休息、洗浴、更衣、收納等生活節點，確認相關物件在同一使用半徑內，而不是為了構圖被拆散。

玄關是硬例：主門、落塵/換鞋區、鞋櫃/鞋、掛鉤/傘架必須形成同一入口節點。若主門在右上，鞋櫃與鞋卻在左偏中間，畫面即使漂亮也 Fail，因為人進門後無法合理換鞋與放物。

審圖時加問：

- 人從入口進來，第一步在哪裡換鞋、放傘、掛外套或放包？
- 使用點與收納點是否相鄰，例如浴室和毛巾/浴袍、床和床頭櫃、工作桌和椅/電腦？
- 是否需要穿越私生活區或主要家具障礙，才能完成入口、洗浴、換衣等日常動作？

若生活節點拆散，回到格局重做；不要只移動單一物件。

---

## §4 常見 AI 空間錯誤圖鑑

### 實戰踩過（等角剖面宿舍場景案例）
1. **斷頭樓梯**：樓梯下端被冰箱堵死／懸空不落地；上端沒有對應樓板開口。
2. **盒中盒不連通**：上下（或左右）兩區各自密封，無任何門洞／樓梯連通，實為兩個獨立盒子。
3. **濕區錯置**：更衣間直接裸開在健身器材旁；無獨立換衣間＋淋浴間（即使不需隱私，機能上也不成立——濕身無處沖洗、衣物無處存放）。
4. **幽靈門排**：玄關進門是鞋櫃，鞋櫃後憑空一排門，每扇都說不出通往哪。
5. **牆體交疊生未知空間**：大門後牆壁互相交疊，圍出進不去的謎之空腔。

### 等角剖面（isometric cutaway）特有結構假影（2026-07-07 由紀層 v1→v2 實戰）
12. **懸空門（floating door on cutaway edge）**：門扇長在被剖除的開放邊緣，一側或兩側無牆體，像貼在空氣裡。成因＝模型把門當獨立裝飾件擺放，剖面切掉近側牆後門失去依附卻仍被畫出。對策：prompt 明寫「每扇門嵌在一段實牆中、門洞左右有牆垛上有門楣；被剖除的開放邊上不得有門」＋AVOID `floating doors on open edges`。**更穩＝要互動的門底圖只畫乾淨門洞／凹龕、不讓模型畫門片**（門扇由己方離散件疊上，順便拿到開關門互動）。驗收：逐扇問「這扇門左右兩側各是什麼牆？」答不出＝懸空。
13. **截短門（shortened door）**：某扇門（常是衛浴等次要小間）被畫矮一截、上緣不及門楣。成因＝模型對次要空間降權縮小、缺統一門高錨。對策：prompt 綁死「全圖每扇門淨高一律＝門高錨（例 130px≈2.05m≈站姿人物 6/5），特別點名易被縮的那扇」；改「只畫足高門洞」可根治。驗收：拿人物尺規比每扇門，各門上緣應等高齊門楣。
14. **幻影光斑（phantom light patch）**：地板出現硬邊窗格光斑，但正上方保留牆無窗；或近側房的窗牆已被剖除、光斑卻留著。成因＝模型學到「暖光地板＝好看」到處灑窗形光斑，未與真實窗位綁定。對策：prompt 綁「硬邊窗格光斑只出現在真實窗正下方投影、帶該窗窗框分割影、全圖單一光向；沒窗的地面不得有窗形光斑；室內燈只做柔和圓暈」。**設計期就避開把窗畫在會被剖除的近側牆**——近側房採光改「柔和無框漫光」，不畫窗格。驗收：對每片光斑反查正上方保留牆是否真有窗；剖除側房不應有硬邊窗格斑。

### 研究補充（文獻＋工具實測常見）
6. **樓梯佔地低估**：AI 給的樓梯水平投影常只有實際需求的一半（40 sq ft → 只畫 20–25），視覺上「幾步就上樓」。
7. **門開進障礙**：門開向撞櫃體／開在牆角轉不開；浴室只能穿過臥室衣櫃進入之類的荒謬鏈路。
8. **走道過窄＋家具比例失真**：看起來對、實際人過不去；沙發比床大、桌子比門高。
9. **投影系統崩壞**：同一張圖多套消失點／等角軸混用，牆線歪斜波浪、接縫對不上——這是「AI 沒有 3D 模型」的直接證據。
10. **窗戶失效**：窗開在內牆、被鄰棟／櫃體貼死，或居室完全無採光開口。
11. **元素數量隨機**：要求 4 床位出 3 個、要求 2 衛出 1 個——指定數量的元素只有碰運氣才對，產後必數。

---

## §5 修正 prompt 措辭範例

> 本節措辭即「負約束配替代」句式的室內版——禁止某錯誤時同時明說正確狀態（不寫 no blocked stairs，寫 stairs land on open floor）。此句式經 A/B 實測：只寫禁止句而不給替代狀態時，模型常把該區域畫成空白或改畫別的錯誤。

### 通用正向約束（附加到任何室內圖 prompt 尾端）
```
architecturally coherent and livable layout, every room connected to the
circulation path by a clearly visible door or opening, single continuous
staircase with clear open landings at both top and bottom (bottom lands on
open floor, top connects through a real floor opening), all doors lead to
defined rooms, bathroom and shower enclosed in its own walled room with a
door, changing room adjacent to shower behind a door, walkways at least
90cm wide and free of furniture, no furniture blocking any door or stair,
walls form closed simple shapes with no overlaps and no inaccessible voids,
one consistent isometric projection (parallel lines stay parallel)
```

### 通用負向（negative prompt／或寫成 avoid 子句）
```
impossible architecture, disconnected sealed rooms, stairs leading to a wall
or blocked by furniture, floating staircase with no landing, doors to
nowhere, row of mysterious doors, overlapping or intersecting walls,
inaccessible void spaces, furniture clipping through walls, blocked walkway,
open-air changing area next to gym equipment, mixed vanishing points
```

### 逐錯誤修正句（哪項 Fail 補哪句）
| 錯誤 | 修正措辭（英文，給影像模型） |
|------|------------------------------|
| 斷頭樓梯 | `the staircase bottom step lands on open empty floor with a clear landing area, nothing placed in front of the stairs, the refrigerator is on a wall away from the staircase` |
| 上下不連通 | `the upper level and lower level are connected by the staircase through a visible opening in the upper floor slab` |
| 濕區錯置 | `a private changing room with lockers directly adjacent to an enclosed shower room, both behind doors, separated from the gym area by a wall` |
| 幽靈門排 | `only draw doors that lead to actual rooms shown in the cutaway; the entrance opens into a foyer with a shoe cabinet on the side wall, then directly into the living area` |
| 牆體交疊 | `simple rectangular room boundaries, every enclosed area is an accessible room, no leftover gaps between walls` |
| 樓梯太迷你 | `full-size residential staircase, approximately 12-14 steps, occupying a realistic footprint` |
| 元素數量 | 把數量寫死並要求可數：`exactly four beds, exactly two enclosed bathrooms`（產後仍要人工數） |

### 結構化寫法（最有效的預防）
先在 prompt 裡用一句話宣告拓撲（房間清單＋連通關係，用 §1 原則設計），再描述風格：
```
Isometric cutaway of a staff dormitory. Layout logic: entrance foyer (shoe
cabinet) → common living/dining area with kitchenette (work-triangle
kitchen) → hallway → sleeping area with four beds; enclosed bathroom with
shower + adjacent changing room off the hallway as one wet zone; a single
staircase from the living area leads up through a floor opening to the
upper lounge, storage built under the stairs. The entrance view is framed
toward the living area window. [風格描述...] [通用正向約束...]
```

---

## §6 主要依據來源

- IRC R311.7 樓梯規範（兩端平台 ≥36in／914mm、淨高 6'8"、門不得侵入平台過半）
- 廚房黃金三角與通道寬度：三邊合計 13–26ft、操作走道 42–48in（NKBA 慣例，cliqstudios／mkdkitchenandbath 等）
- 空間規劃基礎：circulation 無死路、zoning 公私分離、乾濕分離（First in Architecture／BibLus／ArchitectureCourses）
- 視線與焦點：進門視軸、門洞如畫框（Homes & Gardens／Gluckstein）
- 採光策略：borrowed light 室內窗／clerestory／天窗（Architect Magazine／HMC Architects）
- 留白：negative space 防擁擠毀尺度（Homes & Gardens／Houzz）
- AI 平面圖錯誤實測：樓梯佔地低估、建築幻覺、窗戶失效（designdrafter.com、aihomebuilding.com、maket.ai）
- AI 影像幾何缺陷：多消失點、無 3D 世界模型（arXiv 2304.06470、2512.07504 ControlVP）

> 註：走道 90cm、家具佔地 3–4 成等為業界經驗值（設計慣例），非法規；樓梯平台與淨高為法規（IRC）。

# 像素藝術基本功與品質驗收準則（Pixel Art Fundamentals）

> 定位：**AI 產圖驗收與人工清稿的理論地板**。本 Skill 的並排比對驗收（SKILL.md §2）解決「像不像這個遊戲」，本檔解決「是不是合格的像素畫」——兩層都過才算過。
> 引用者：`sprite-prompt-engineer`（產前把準則寫進 prompt）、`game-visual-storyteller`（風格定調時鎖死 §1 五參數）、驗收流程（§6 機械檢出＋§8 人眼 rubric）。

---

## §1 專案開工五參數 style guide（所有產圖驗收對照此檔）

每個像素專案**開工前寫死五個參數**，之後所有產圖、驗收、清稿都對照它。任一參數中途漂移＝整批風格違規。

### 1.1 畫布（render resolution）——預設 640×360

- 320×180 與 640×360 是現代像素遊戲兩大主流基準解析度，因為可**整數倍縮放**到所有 16:9 顯示器：
  - 320×180 → ×4=720p、×6=1080p、×8=1440p、×12=4K
  - 640×360 → ×2=720p、×3=1080p、×4=1440p、×6=4K
  - 480×270 → ×4=1080p、亦可 ×8 到 4K（折衷檔）
- 整數倍縮放確保每個藝術像素對映到整數個螢幕像素，避免內插模糊與不均勻像素。
- **本管線預設 640×360**：視野寬敞、細節空間夠，且 ×3 直上 1080p。

### 1.2 tile／角色格——慣例 16 tile ＋ 32 角色

| 角色格 | 典型用途 |
|---|---|
| 16×16 | 俯視 RPG／roguelike 小角色、道具、投射物；新手起點 |
| 24×24 | 16 與 32 的折衷，常見於平台遊戲 |
| 32×32 | 「工作馬」尺寸：放得下臉、手持物、完整明暗 ramp |
| 48×48 | 較高細節主角／敵人 |
| 64×64+ | Boss、頭像 portrait、盔甲布褶等高細節；一般角色用已「接近過大」 |

- **像素密度一致性**是搭配關鍵：全場景「一個藝術像素＝相同螢幕像素數」——角色 32×32 以 3x 顯示，背景 tile 也必須以 3x 顯示。同畫面出現兩種密度＝立即違規。
- 選格方法論（Pixel Parmesan）：問兩個問題——「最小必要細節是什麼（角色通常是臉部五官）？」「該風格需要幾個像素才畫得出這個細節？」原則：**猶豫時選更小**；過大的解析度誘使人塞噪點。
- 搭配速查：320×180 配 16–24px 角色（tile 16）；**640×360 配 32–48px 角色（tile 16 或 32）**；480×270 配 24–32px。

### 1.3 母調色盤——指定一個，全專案落盤

| 調色盤 | 色數 | 作者／出處 | 特性 |
|---|---|---|---|
| [DawnBringer 32（DB32）](https://lospec.com/palette-list/dawnbringer-32) | 32 | DawnBringer（Pixel Joint） | Aseprite 內建預設之一；社群公認經典，限制嚴、風格強 |
| [Resurrect 64](https://lospec.com/palette-list/resurrect-64) | 64 | Kerrie Lake | Lospec 下載 33 萬+；ramp 相鄰排列、涵蓋全色相家族，各色相約 5 色一組——**本管線預設**（色域廣且 ramp 結構清楚） |
| [Apollo](https://lospec.com/palette-list/apollo) | 46 | AdamCYounis | 下載 19 萬+；tag「16bit / linear」，藍綠棕紅紫灰各自成 ramp、暗→亮線性排列 |

- 皆可於 Lospec 直接下載 PNG／PAL／ASE／GPL／HEX 等格式（Lospec 收錄 4300+ 調色盤，是像素圈事實上的調色盤標準庫）。
- 想更嚴（色少風格更硬）走 DB32 或 Apollo；預設 Resurrect 64。

### 1.4 outline 策略——四選一寫死，混用即風格漂移

| 策略 | 特徵 | 適用 |
|---|---|---|
| 黑邊（hard black outline） | 全周黑線，可讀性最高、略重、卡通／UI 感 | 角色要從複雜背景跳出來；新手起點 |
| 有色外框（colored outline） | 用該區域最深色代替黑 | 柔和一點的卡通感 |
| Selective outline（sel-out） | 外框顏色隨光照變化：受光側用亮色或乾脆斷開、背光側用深色 | 「職業預設」——輕又可讀，自然感 |
| 無框（no outline / lineless） | 靠色塊對比撐剪影 | 簡潔背景、現代風；與背景分離差 |

- Sel-out 基本做法：取 sprite 邊緣像素的顏色再降一階當外框色；受光處提亮或移除。學習路徑：先畫穩黑邊，再進階 sel-out。
- **outline 策略是專案級風格參數**：同批資產混用（有的黑邊有的無框）＝一致性違規，這是 AI 產圖最常見的風格漂移之一。

### 1.5 dithering 政策——角色臉部禁用、大面積漸層才用

- 原理：兩色交錯排列，視覺混成盤外的中間色——限色下模擬色深。
- **該用**：大面積漸層（天空、金屬、光衰減）、材質感（石、土、布、鏽）、色盤實在加不了色時。
- **不該用**：16×16 以下小 sprite（沒空間讓 pattern 成立）；**臉部與關鍵剪影**（要乾淨色塊不要紋理）；追求現代乾淨平塗風時。
- 風格相依：GB 4 色風幾乎必用、NES 風大量用、HD-2D／高解析風幾乎不用。
- Pattern 選型：Bayer／ordered 適合大面積平滑漸層；手工 dither 適合單一物件塑形；noise dither 只當紋理用、極易過量。
- **本管線預設**：角色（16–48px）**禁用 dithering**；僅場景大面積漸層允許 50% checkerboard 以內的 ordered dither。AI 產圖若在角色皮膚／臉上出現 dither＝退修。

### 1.6 可直接抄的 style guide 模板

```toml
# style_guide.toml — 專案開工五參數，全程對照
canvas          = "640x360"        # x3 → 1080p，整數縮放
tile            = 16
character_grid  = 32               # 主角/NPC；boss 允許 64
palette         = "resurrect-64"   # https://lospec.com/palette-list/resurrect-64
outline         = "selout"         # 全專案統一；不得混用
dithering       = "scene-only"     # 角色/臉部禁用
aa_outer_edge   = false            # 透明資產外緣禁 AA（見 §4）
```

---

## §2 調色盤紀律

### 2.1 為什麼限色

- 「每個顏色都要有自己的身分，做最多的工作」（Derek Yu）——顏色太多且相近會互相稀釋、物件難以區分。
- 色數越多，整體 cohesion 越難維持；單件從 4–8 色起步：主色一條 ramp ＋ 一個 accent。
- 限色也是**風格一致性的機械化檢查點**：成品上任何不在母盤內的顏色都算違規（AA 用色也應取自盤內）。

### 2.2 Ramp 設計與 hue shifting

- Ramp＝一組由暗到亮、可互相銜接的顏色，多數像素畫每條 ramp 用 **3–5 色**。
- **Hue shifting**：陰影不只是變暗——往冷色（藍／紫）偏移並**降飽和**；亮部往暖色（黃／橙）偏移並**提飽和**。
- 純明度直落的「**straight ramp**」顯得髒濁、且難與其他色相的 ramp 調和——這是 AI 產圖與新手共通的病。
- 避免「naive coloring」：樹葉純綠、天空純藍、石頭純灰是新手標記；現實顏色因反射光而複雜，直接借用成熟母盤再微調是正路。

### 2.3 驗收規則

1. 所有資產 `色數 ≤ 母盤` 且 100% 落在盤內——用 §6 的 PIL 片段機械化檢查。
2. 單一 32×32 角色實用色數建議 8–16 色；抽查任一 ramp 是否有 hue shift（同 ramp 各色 hue 值應遞移，非只有 V 變化）。

---

## §3 Cluster 理論與線條

（來源：saint11 #2 – Cluster Sketching and Painting）

- **Cluster**＝同一顏色的連續像素群（斜角相連算「弱連接」）。
- 核心準則：**cluster 越少越好**——同一色區破碎成多個小 cluster（該合併而未合併）＝噪點。
- **orphan pixel（孤立單像素 cluster）禁令**：孤兒像素是畫面「噪、亂」的主因。需要小細節時，用 2–3 像素的小形狀取代單像素。
  - **例外**：材質紋理、AA、刻意的強調點（如眼睛高光）可以容許。
- Cluster sketching 工作流：先鋪大色塊 → 逐步細修邊緣 → 最後修 jaggies、加細節（類似傳統繪畫的塊面法）。
- **Jaggies 判別**：cluster 邊界要遵守幾何邏輯——曲線的**階梯步長須單調遞增／遞減**；步長不合邏輯地亂跳（1,3,1,2…）＝jaggies，線條看起來有毛刺。
- 驗收：放大 8x 掃描，非刻意高光／紋理區出現孤兒像素即退修；沿外框走一圈找步長亂跳。

---

## §4 Anti-aliasing（AA）準則

- AA＝在線條與背景間放中間色，用「感知明度」的微移打破網格感。中間色**優先重用 sprite 既有顏色**、可帶 hue shift，不是數學平均。
- 放置規則：
  - 只對**步長 > 1 像素**的階梯做 AA；**45° 線（1-1 階梯）與純直線不做 AA**。
  - 長段用多層 AA（stacked AA）：越靠原色的 AA 像素越多，靠背景越少；「段越長、AA 越長」。
  - 各層 AA 長度要有變化——**等長平行的 AA 帶反而強化網格＝banding**。
- **不做 AA 的時機**：
  - 極小 sprite（AA 變噪點）；
  - 遊戲 sprite 的**透明外緣**（背景會變，外緣 AA 對某些背景會髒掉——外緣 AA 只適合固定背景的單張插畫）；
  - 大而平緩的線本來就不需要。
- 過度 AA（halftone 太多、步數太多）＝糊。AI 產圖常見「全圖無差別柔邊」＝過度 AA，直接退。
- 機械檢查：透明背景資產外緣必須硬邊——alpha 通道只允許 0/255（見 §6）。

---

## §5 Sub-pixel animation（清稿加分項，非必過項）

- 定義：**不移動像素、改變像素顏色**來表現小於 1 px 的位移——本質是「把 AA 拿來做動畫」。
- 主要技法：**value/color tweening**——在幀間漸變邊緣像素的明度，讓輪廓「看起來」滑過去，剪影本身不動。
- 用途：低解析度下讓呼吸、髮絲飄動、緩慢移動不會一格一格跳；輪廓微移而不改 silhouette。
- **對 AI 管線的含意**：sub-pixel 是逐幀手工技藝，目前 AI 產動畫幀基本做不到。驗收動畫時只要求「整像素位移平順、無抖動」；sub-pixel 潤飾列入**人工清稿階段的加分項，不列必過項**。

---

## §6 常見錯誤圖鑑＋機械檢出

### 6.1 錯誤圖鑑

| # | 錯誤 | 定義 | 主要出處 |
|---|---|---|---|
| 1 | **Mixels** | 同圖中混用不同大小的「像素」，或像素不對齊網格；常因放大後用 1px 筆刷續畫、或旋轉／非整數縮放造成。**AI 產圖幾乎必有**，清稿第一步就是抓它 | The Art of Yari、tofupixel |
| 2 | **Pillow shading** | 從外框往內一圈圈變亮的「枕頭狀」明暗，無光源方向，糊而無形體 | Derek Yu |
| 3 | **Banding** | 相鄰色帶的邊緣像素逐格平行貼齊（含等長 AA 帶），強化網格感、破壞光照方向。修法：壓縮過渡帶、把漸層方向轉成順著坡面 | saint11 #5 |
| 4 | **Jaggies** | 曲線階梯步長亂跳（判別法見 §3） | saint11 #2、Pixel Joint |
| 5 | **Orphan pixels / doubles** | 孤立單像素噪點（§3 禁令）；doubles＝斜線上不必要的雙像素塊 | saint11 #2 |
| 6 | **單像素細肢** | 手臂／腿／樹枝只有 1px 寬，無法上明暗、無體積 | Derek Yu |
| 7 | **太多相近色** | 色彩失去個別功能、畫面髒（§2） | Derek Yu |
| 8 | **Naive coloring** | 用「純色」直覺填色（純綠葉、純藍天）（§2.2） | Derek Yu |
| 9 | **過度 AA／過度 dither** | 糊、噪（§4、§1.5） | Pixel Joint、Pixnote |

另補 AI 產圖特有病（與上表同源同判法）：**假像素**（看起來像像素但沒 snap 到一致格點，引擎內縮放糊成一團）、**像素密度不一**（同圖單顆「像素」6px、7px 寬混雜）、**無真 alpha／背景色暈邊**（描邊 sprite 外圈一圈髒色）——全數落在 mixels＋alpha 檢查的檢出範圍內。

### 6.2 機械檢出（先過腳本，才進人眼）

四道機械前哨，全部可程式判定：

1. **原生解析度往返測試（抓 mixels）**：把圖縮到宣稱的原生解析度再放大回去，與原圖不一致＝存在 mixels。
2. **色盤白名單比對**：所有不透明像素 ∈ 母盤 hex 清單。
3. **alpha 二值檢查**：alpha 只允許 0/255（外緣硬邊，§4）。
4. **色數上限**：unique colors ≤ 母盤色數（真像素≤數百色；AI 自評「真像素」實測常是 17–20 萬色 faux-pixel，自述不可信）。

可直接抄的 PIL 檢查片段（完整現成程式見研究報告 05 附錄 `palette_check.py`）：

```python
from PIL import Image

def check(path, palette_hex, native_size):
    img = Image.open(path).convert("RGBA")
    px = list(img.getdata())
    # 1. alpha 硬邊：只允許 0/255
    bad_alpha = {p[3] for p in px} - {0, 255}
    # 2. 色盤白名單（不透明像素）
    allowed = {tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in palette_hex}
    off = {p[:3] for p in px if p[3] == 255} - allowed
    # 3. mixels：縮到原生格再放大回來，應與原圖逐像素相等
    down = img.resize(native_size, Image.NEAREST)
    up = down.resize(img.size, Image.NEAREST)
    mixels = list(up.getdata()) != px
    return {"bad_alpha": bad_alpha, "off_palette": len(off), "mixels": mixels}
```

其他目測法（機械測不了、進 §8 人眼 rubric）：**光源方向測試**——指出圖中光源位置，指不出來或每個物件方向不同＝pillow shading／光照不一致；**banding 沿邊掃**——沿色帶邊界看相鄰兩色階梯是否逐格平行貼齊。

---

## §7 AI 產圖清稿 SOP

AI 原圖（高解析假像素）到合格資產的固定五步：

1. **Downscale 到原生格**：先做格點偵測（unfake.js／pixeldetector 類工具，或已知倍數直接整數縮），一律 nearest／point 或 content-aware 取樣，**絕不用 bilinear／Lanczos**；放大回遊戲尺寸只能整數倍 nearest neighbor。
2. **Quantize 到母盤**：量化到 §1.3 指定母盤（Aseprite、PIL quantize 或 `magick -dither None -remap palette.png`）；k-means 自由量化易產生「泥色」，**指定 palette 結果較穩**。
3. **手修 jaggies／orphan pixel**：照 §3 準則——階梯步長修成單調、孤兒像素併入 2–3px 小形狀或刪除；同步檢 doubles、banding。
4. **補 sel-out（或專案指定的 outline 策略）**：照 §1.4 寫死的策略統一外框；透明外緣去 AA 殘邊、alpha 二值化。
5. **1x 原尺寸驗收**：縮回原生尺寸看——**像素畫必須在 1x 成立，只有放大才好看＝失敗**。過了才進 §8 人眼 rubric 與 SKILL.md §2 並排比對。

---

## §8 人眼 rubric（依嚴重度分級）

機械前哨（§6.2）全過之後的人眼關。與 SKILL.md §2 的並排比對驗收**銜接使用**：本 rubric 驗「是不是合格的像素畫」，並排比對驗「像不像這個遊戲的圖」——後者是最後一關且一票否決。

| 級別 | 項目 | 判準 |
|---|---|---|
| 🔴 必退 | Mixels／混像素密度 | 往返測試不過、同圖多種像素大小（機械可檢，人眼複核） |
| 🔴 必退 | 光照方向不一致 | 指不出全圖光源位置，或各物件光源方向互相矛盾 |
| 🔴 必退 | Pillow shading | 明暗從外框往內一圈圈、無方向性 |
| 🟠 退修 | Banding | 色帶邊緣逐格平行貼齊、等長 AA 帶 |
| 🟠 退修 | 孤兒像素成片 | 非刻意高光／紋理區大量單像素噪點 |
| 🟠 退修 | Outline 策略漂移 | 與 style guide 寫死的策略不符、同批混用 |
| 🟠 退修 | 臉部 dither | 角色臉部／關鍵剪影出現 dithering |
| 🟡 清稿處理 | Jaggies | 階梯步長亂跳（單處） |
| 🟡 清稿處理 | Doubles | 斜線上零星雙像素塊 |
| 🟡 清稿處理 | AA 過量 | 局部柔邊過度（全圖無差別柔邊升級為 🔴 級退件） |

流程：🔴 任一條＝整張退回重產（清稿救不回）；🟠 退修或清稿期修復；🟡 清稿期順手修。修完重跑 §6.2 機械前哨＋1x 驗收，🔴＋🟠 清零才交付並進並排比對。

---

## 來源

- saint11（Pedro Medeiros）像素教學系列：#2 Cluster（https://saint11.art/pixel_art_articles/article2/）、#5 AA／banding（https://saint11.art/pixel_art_articles/article5/）、#6 Basic Color Theory（https://medium.com/pixel-grimoire/how-to-start-making-pixel-art-6-a74f562a4056）
- Derek Yu – Pixel Art Common Mistakes：https://www.derekyu.com/makegames/pixelart2.html
- Lospec（調色盤標準庫／outline 教學／quantizer）：https://lospec.com/ ・ https://lospec.com/articles/pixel-art-outlines ・ https://lospec.com/palette-quantizer/
- Pixel Parmesan：Choosing the Right Resolution（https://pixelparmesan.com/blog/choosing-the-right-resolution-for-your-pixel-art）、AA Fundamentals（https://pixelparmesan.com/blog/anti-aliasing-fundamentals-for-pixel-artists）
- SLYNYRD Pixelblog #1 – Color Palettes：https://www.slynyrd.com/blog/2018/1/10/pixelblog-1-color-palettes
- The Art of Yari – About Mixels：https://yari-pixels.github.io/Articles/mixels.html
- 2D Will Never Die – Sub-pixel Animation：https://2dwillneverdie.com/tutorial/give-your-sprites-depth-with-sub-pixel-animation/
- Pixnote（dithering／sel-out）：https://pixnote.net/en/learn/dithering/ ・ https://pixnote.net/en/learn/outlines/

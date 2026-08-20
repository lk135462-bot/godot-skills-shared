# AI 像素產圖工具版圖與後處理管線

> ⚠️ **時效敏感**：本文為 **2026-07 快照**。AI 產圖工具迭代極快，重大選型（換供應商、簽訂閱、改管線）前先 WebSearch 覆核現況（定價、模型版本、功能上限都可能已變）。

**引用時機**：要決定「這批素材用哪個工具生」時讀 §1–§2；拿到 AI 原圖要清洗成真像素時讀 §3；驗收時讀 §4（與 SKILL.md §3 鐵則 5「量化驗證」、`pixel-art-fundamentals.md` §6 PIL 前哨銜接）。

---

## §1 工具版圖（2026-07）

### 1.1 PixelLab（pixellab.ai）——專用：角色動畫／旋轉視角

像素遊戲素材一站式生成：角色、動畫、4／8 方向旋轉視角、tileset、inpainting。

- **骨架動畫是獨門**：Animate with Skeleton 手動定義關節逐幀控制，**骨架可存成 Aseprite 檔**重用到其他角色；另有文字→動畫（"walking cycle" 一句話生成）與動畫轉移（既有動畫套到新角色）。
- **動畫畫布上限**：skeleton 動畫接受固定畫布 16×16／32×32／64×64／128×128／**256×256**（2026-07 官方文件；舊評測所稱「上限 128×128」已過時）。非標準體型／高度風格化角色動畫容易出錯。
- **定價（含商用授權）**：$12/月（圖上限 320×320，含動畫＋地圖工具）／$24/月（優先佇列、400×400、實驗性工具）／$50/月（最高優先、20 併發、團隊協作）；免費試用 40 次快速生成。
- **介面**：Web app、Aseprite plugin、**API＋MCP server**——意味著 Claude/agent 可直接派工：

```bash
# 需先於 pixellab.ai 取得 API token；呼叫需帶 Authorization header，否則加得進伺服器但呼叫會靜默 auth 失敗
claude mcp add pixellab https://api.pixellab.ai/mcp -t http --header "Authorization: Bearer $PIXELLAB_TOKEN"
```

### 1.2 Retro Diffusion（retrodiffusion.ai）——專用：量產靜態素材／tileset

「真像素」導向的自訓模型（訓練資料為 Astropulse 與其他像素藝術家**授權同意**的素材，商用風險較低），輸出貼近硬格點對齊、無抗鋸齒。

- **模型家族**：RD Fast（快速迭代）／RD Plus（旗艦，原生 ≤256×256）／RD Pro（最高細節＋參考圖）／RD Tile（無縫貼圖）／RD Animation（固定佈局 sprite sheet：四方向 walk cycle、idle、VFX 序列）。
- **關鍵特性**：**palette 鎖定**（限制輸出到指定 16／32 色調色盤）、格點尺寸控制、Aseprite extension、API（官方或 Replicate／Scenario／Runware 聚合平台）。
- **定價**：freemium＋儲值制，多數單圖成本 **<$0.01**（1 credit ≈ 一張 ≤276×276）。
- **注意**：官方坦承「完美方格與嚴格色數」在生成階段仍**非 100% 保證**，靠訓練資料＋專有後處理補足——**仍需過 §4 驗收**，不能免檢。

### 1.3 GPT Image 2（OpenAI，2026-04-21 發布）——通用模型中最能守規則

- 通用模型中**邊緣最硬、palette 遵守最嚴**（指定調色盤當硬規則）；「style anchor prompt＋@ 參考首張 idle 圖」可維持跨批次一致。
- **弱點**：直接要整張 sprite sheet **常缺幀／重複姿勢**——一次一姿勢、以參考圖串聯，別一次要整張 sheet。

### 1.4 Gemini（Nano Banana Pro）——三大硬傷，只能靠 workaround

1. **無真 alpha**：要求透明背景會得到棋盤格／白底／黑底，永遠是平面 RGB。
2. **AA 烤色**：抗鋸齒混色烤死在邊緣，深底＋黑描邊 → 髒色暈邊。
3. **格點不 snap**：prompt 裡怎麼喊都不會 pixel-snap，必須後處理。

**實測有效的 workaround**：`#00FF00` 純綠底（prompt 用大寫 CRITICAL 強調＋明令 no gradients/noise/shadows）＋ sprite 外圈 **2–3px 白描邊**當緩衝帶 → 後處理 **HSV 去背**（hue ±22°、sat ≥0.3、val ≥0.3）——白邊讓抗鋸齒混向白色而非背景色。sprite sheet 需內容感知切割（偵測連通透明區域），不能均勻格切。複雜連段動作一致性崩壞，簡單動作可用。

### 1.5 Flux／SDXL＋pixel LoRA（本地開源）——可控性最高，一致性仍不穩

- Flux.1／Flux.2 Klein、SDXL、Qwen-Image 都有 pixel art LoRA；**spritesheet LoRA 已出現但不成熟**（2026-02 Flux.2 Klein 4-Walk spritesheet LoRA 作者自述：頭飾被裁、非人角色解剖錯誤、背面列一致性差）。
- 優勢在全鏈路可控：ComfyUI 內串 ControlNet／IPAdapter／自訓角色 LoRA；原始輸出一律是「假像素」，品質上限取決於後處理（§3）。

---

## §2 選型決策

| 需求 | 首選 | 理由 |
|---|---|---|
| walk cycle 等**標準動畫**（既有角色、常見動作） | **PixelLab**（skeleton） | 唯一有骨架級控制、骨架可存 Aseprite 重用；≤256×256 生產可用。**別再用通用模型硬生 sprite sheet** |
| **量產靜態小素材／icon／tileset** | **RD API** | 原生格點乾淨、單張 <$0.01、palette 可鎖——適合 fan-out 批量產＋機械驗收 |
| **本地 ComfyUI（RTX 5090）**、要角色 LoRA 一致性 | **Flux＋角色 LoRA**，管線尾掛 `ComfyUI-PixelArt-Detector` | 生成即修復一條龍、免 API 費，與 LoRA 一致性路線互補 |
| 概念探索、一次性大圖 | 通用模型（GPT Image 2 優先） | 指令遵循強，但需完整走 §3 後處理；**通用模型只做概念／一次性，不進量產線** |

---

## §3 後處理標準流

AI 原圖（高解析假像素）→ 真像素素材的固定流程：

```text
① 格點偵測          unfake.js（runs-based / edge-aware）或 Astropulse/pixeldetector
② grid snap＋整數 downscale   content-aware（dominant 起手；漸層多試 median）——每邏輯像素恰映射 1 輸出像素
③ palette 量化       unfake.js 內建 libimagequant（WASM）＋自訂固定 palette
                     （k-means 自由量化易產「泥色」，鎖定 palette 較穩）
④ alpha 二值化       去半透明邊緣（alpha 只留 0/255）＋形態學去噪
⑤ 機械驗收           見 §4
```

**工具對照**：

| 工具 | 形態 | 能力 |
|---|---|---|
| [unfake.js](https://github.com/jenissimo/unfake.js/) | 瀏覽器／JS lib | 格點偵測＋content-aware downscale＋libimagequant 固定 palette＋alpha 二值化，一站式 |
| [Astropulse/pixeldetector](https://github.com/Astropulse/pixeldetector) | Python CLI | 偵測真實解析度並 downscale 還原（RD 作者出品），適合接進 Python 批次腳本 |
| [ComfyUI-PixelArt-Detector](https://github.com/dimtoneff/ComfyUI-PixelArt-Detector) | ComfyUI 節點 | pixeldetector 節點化＋從圖片載入 palette，掛 workflow 尾端 |
| [Lospec Palette Quantizer](https://lospec.com/palette-quantizer/) | Web | 上傳圖→量化到 Lospec 任一調色盤 |

**ImageMagick 一行版**（palette 用 Lospec 下載的 PNG 1x）：

```bash
magick in.png -dither None -remap palette.png out.png
```

**Downscale 鐵律**：一律 nearest/point 或 content-aware（dominant color per cell），**絕不用 bilinear／Lanczos**；放大回遊戲尺寸只能整數倍 nearest neighbor。

---

## §4 品質陷阱與機械驗收

### 4.1 陷阱清單

| 陷阱 | 表現 |
|---|---|
| **假像素** | 「看起來像像素」但沒 snap 到一致格點，引擎內縮放後糊成一團 |
| **像素密度不一** | 同圖內單顆「像素」6px、7px 寬混雜，均勻格切必爆 |
| **AA 殘留暈邊** | 邊緣半透明／混色像素；黑描邊＋深背景 → 髒色暈邊 |
| **palette 爆量** | AI 偷加微漸層／子像素噪聲，unique colors 破萬（自稱真像素實為 17–20 萬色，見 SKILL.md 鐵則 5） |
| **sheet 幀漂移** | 各幀比例／位置漂移、佔格寬度不一、缺幀重複幀；跨批次同角色配色漂移 |

### 4.2 機械驗收（可程式判定，取代目視自述）

```text
□ 格點：nearest 4x/8x 放大目視——每顆邏輯像素恰為 N×N 實像素、無半顆像素
□ 色數：unique colors ≤ 目標 palette 數（magick identify -format %k out.png）
□ alpha：二值檢查——alpha 通道只有 0/255 兩值，邊緣無半透明像素
□ 整除：影像寬高可被邏輯格尺寸整數倍整除；格點偵測出的倍數為整數
□ sheet：各幀腳底基線對齊、幀數正確無重複、逐幀播放無跳動
□ 一致性：與同套既有素材並排比對（風格、描邊、光源方向、飽和度）
```

前四項可直接寫進腳本自動判定——與 `pixel-art-fundamentals.md` §6 的 PIL 前哨檢查銜接（同一組量化手段），落實 SKILL.md 鐵則 5「產圖自評不可信，用量化驗證」。

---

## 來源／互鏈

- 本 Skill：`SKILL.md` §3 鐵則 5（量化驗證）；`References/pixel-art-fundamentals.md` §6（PIL 前哨）

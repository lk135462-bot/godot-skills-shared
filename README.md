# Godot 遊戲製作 Skills ＆ Agents

給 Claude Code 用的 **Godot 4 遊戲開發知識包**：3 個 Skill ＋ 10 個專職 Agent，
涵蓋「七大遊戲類型的系統實作模式」「AI 產圖 → 引擎落地的美術管線」「室內場景空間合理性把關」。

內容沉澱自數個實際 Godot 4 專案（回合制策略、抽卡塔防、像素等角模擬），
每條鐵則都是踩過坑之後才寫進來的——**不是從官方文件抄的教學**。

---

## 這包裡有什麼

### Skills（3）

| Skill | 一句話 | 規模 |
|---|---|---|
| **`godot-game-dev`** | Godot 4 七大遊戲類型開發指南路由器：RPG／塔防／策略／4X／平台跳躍／Roguelike／視覺小說，各一份 800–2,000 行完整實作模式；另含像素呈現、架構紀律、資源檔安全、驗證工具鏈四份橫切面指南 | 11 份指南 ＋ vendor 原文 |
| **`pixel-game-scene-pipeline`** | AI 產圖怎麼變成引擎裡「活的、統一光影的、可互動的」遊戲場景：設計先行 → 生成譜系複用 → 管線決策樹 → 並排驗收 → 引擎疊層，含 12 條鐵則 | 1 份主文 ＋ 2 份 References ＋ vendor |
| **`interior-space-sanity`** | 室內／建築場景圖的空間合理性把關：八大空間運用原則（含 prompt 措辭）＋ 七大合理性檢核 ＋ AI 空間錯誤圖鑑。**`pixel-game-scene-pipeline` 的硬相依** | 1 份主文 |

### Agents（10）

| Agent | 職責 |
|---|---|
| `godot-gameplay-scripter` | GDScript 遊戲邏輯：戰鬥／AI／技能／波次／狀態機／存檔 |
| `godot-shader-developer` | Godot 4 shader 與視覺特效，60fps 是最重要的視覺效果 |
| `game-technical-artist` | 美術資產進引擎：Sprite Sheet 打包、Atlas、AnimationPlayer、匯入參數 |
| `game-designer` | 機制設計、數值平衡、經濟系統、成長迴圈 |
| `game-visual-storyteller` | 角色設計書、場景視覺規劃、像素風格 style guide 定義權 |
| `level-designer` | 關卡／地圖／戰術空間／玩家動線 |
| `narrative-designer` | 劇情架構、對話系統、分支敘事 |
| `game-audio-engineer` | 互動式音樂系統（Godot 4.3+ `AudioStreamInteractive`）、音效設計 |
| `sprite-prompt-engineer` | 角色立繪 ＋ 像素素材的 AI 產圖 prompt 與工具選型 |
| `blender-addon-engineer` | Blender add-on／asset validator／exporter，DCC 管線自動化 |

---

## 安裝

Skills 與 Agents 分別放進 Claude Code 的設定目錄即可。

**Windows（PowerShell）**
```powershell
.\install.ps1            # 複製到 ~\.claude\skills 與 ~\.claude\agents
.\install.ps1 -Link      # 改用符號連結（要系統管理員或開發者模式），之後 git pull 即同步
```

**macOS / Linux**
```bash
./install.sh             # 複製
./install.sh --link      # 改用 symlink
```

**手動**：把 `skills/*` 複製到 `~/.claude/skills/`、`agents/*.md` 複製到 `~/.claude/agents/`。
只想裝其中一兩個就複製那幾個目錄。裝完在 Claude Code 用 `/skills`、`/agents` 確認有被載入。

> 也可以放進**專案內**的 `.claude/skills/`、`.claude/agents/`，讓整個團隊跟著 repo 走。

---

## 怎麼用

**Skill 是被動觸發的**——講到對應情境自然會載入，不用手動叫：

```
「我要用 Godot 做一個塔防，波次系統怎麼設計？」   → godot-game-dev 載入塔防指南
「這張 AI 產的房間圖要接進 Godot，怎麼摳互動件？」 → pixel-game-scene-pipeline
「幫我看這張等角剖面的格局合不合理」              → interior-space-sanity
```

**Agent 用 `@名稱` 叫**：

```
@godot-gameplay-scripter 幫我寫敵人的狀態機
@game-designer 這個抽卡機率曲線合理嗎
```

### 建議的起手式

1. **先確認遊戲類型** → `godot-game-dev/SKILL.md` 的路由表指到對應指南。**不要一次載入全部 7 份**（單份就 800–2,000 行）。
2. **像素風專案**必讀 `References/godot-pixel-art.md`，與類型指南並用（類型指南管系統架構，它管像素呈現層）。
3. **開專案第一天**就把 `References/godot-verification-toolchain.md` 的 headless 驗收鏈建起來——不要等出事才補。
4. **要用 AI 產場景圖**才需要 `pixel-game-scene-pipeline`；純手繪／純程式美術可略過。

---

## 內容的可信度分層（重要）

這包東西刻意區分三種來源，**引用時請看清楚標註**：

| 標註方式 | 意思 | 怎麼對待 |
|---|---|---|
| 引用官方文件／外部一手來源 | 有外部事實依據 | 可直接當事實，但新版 API 仍請對照官方 class reference |
| 「實測」「實戰」「踩過」 | 單一專案的實證結論 | **是有效經驗，不是通則**——換題材／換受眾可能不成立 |
| 「範例」「參數範例」「可調」 | 設計選擇 | 當起點，不當標準 |

例如 `godot-tower-defense.md` LAYER 8 特意把「TD 業界常規」與「某專案的設計選擇」拆成 A/B 兩張表——
前者有外部來源，後者只是一款遊戲的玩測結論。**這個分層本身就是這包東西最想傳達的紀律。**

指南主要在 Godot **4.3–4.7** 上驗證（模式驗證於 4.6.x）。新版 API 變動請對照官方文件。

---

## 邊界（這包做不到什麼）

- **不含美術資產**，也不含任何遊戲專案原始碼——只有方法論與實作模式
- **不含通用型 agent**：`pixel-game-scene-pipeline` §6 的路由表提到 `e2e-testing-engineer`／`ui-ux-reviewer`／`critic`，
  這三個不是 Godot 專屬所以未隨附，自建或以人工 review 替代即可
- **不含 Unreal 相關**（原始收藏中有，但與本包主題無關）
- `pixel-game-scene-pipeline` §4 列的工具腳本是**行為契約規格**，不是現成程式碼——
  請照該節「要點」欄自行實作（那一欄才是踩過坑後定下來的部分）

---

## 授權

本 repo 的**原創內容**（`SKILL.md`、`References/godot-*.md`、`agents/*.md`）可自由使用與修改。

`References/vendor/`、`References/vendor-sprite-forge/` 下是**第三方原文**，各有其授權，
其中 terma 的部分為 **CC-BY-SA-4.0（署名＋相同方式分享）**。
**再散布前請務必讀 [`NOTICE.md`](NOTICE.md)**，並保留各 vendor 目錄內的 LICENSE 檔。

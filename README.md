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
| **`pixel-game-scene-pipeline`** | AI 產圖怎麼變成引擎裡「活的、統一光影的、可互動的」遊戲場景：設計先行 → 生成譜系複用 → 管線決策樹 → 並排驗收 → 引擎疊層，含 12 條鐵則 | 1 份主文 ＋ 2 份 References ＋ **3 支可執行腳本** ＋ vendor |
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

### 做第一個遊戲：從零到能玩的順序

假設你要做一個 2D 遊戲，實際會這樣走。每一步後面是「去讀哪份／叫哪支」：

| # | 做什麼 | 用什麼 | 為什麼是這個順序 |
|---|---|---|---|
| 1 | **決定類型** | `godot-game-dev/SKILL.md` 路由表 | 類型決定架構。RPG 的屬性系統和塔防的波次系統長得完全不一樣，**架構選錯重構成本極高** |
| 2 | **設計玩法**（機制／數值／成長迴圈） | `@game-designer` → 產出 `GAME_FLOW.md` | 觸及 3+ 系統的功能一定要先有設計文件。跳過這步＝一步一試錯 |
| 3 | **建專案骨架** | `References/godot-architecture-discipline.md` §6 專案設置＋§2 場景組織 | Autoload 慣例、`.gitignore`／`.gitattributes`、目錄結構，一開始定好比之後搬便宜 |
| 4 | **架好驗收鏈** | `References/godot-verification-toolchain.md` 第一軌 | **這步最常被跳過也最痛**。`--headless --check-only` 等於 GDScript 的 lint，第一天就要能一行指令知道專案有沒有壞 |
| 5 | **寫核心系統** | 類型指南（如 `godot-tower-defense.md`）＋`@godot-gameplay-scripter` | 指南裡是完整可抄的 GDScript 4.x 模式，不是虛的原則 |
| 6 | **關卡／地圖** | `@level-designer`＋類型指南的地圖章節 | 讓地形服務機制，不是先畫好看再想玩法 |
| 7 | **美術進引擎** | `@game-technical-artist`；像素風加讀 `References/godot-pixel-art.md` | 匯入參數（`filter=Nearest`、stretch mode）錯了畫面就是糊的，這層獨立於玩法 |
| 8 | **特效／shader** | `@godot-shader-developer` | 60fps 優先於好看 |
| 9 | **音效／BGM** | `@game-audio-engineer` | Godot 4.3+ 有內建互動式音樂節點，不必自己寫狀態機 |
| 10 | **劇情／對話** | `@narrative-designer` | 有敘事需求才走 |

**橫切面，隨時可能用到：**

- 手寫或請 AI 代寫 `.tscn`／`.tres` 之前 → **一定先讀** `References/godot-file-format-safety.md`。
  資源檔是嚴格序列化格式不是程式語言，把 GDScript 語法寫進去是 LLM 編輯 Godot 專案最高頻的失敗。
- 卡住 debug → `References/godot-architecture-discipline.md` §5 除錯七步法。
- 要用 AI 產場景圖 → 才需要 `pixel-game-scene-pipeline`。純手繪或純程式美術可以完全略過這個 Skill。

### 兩個最容易踩的坑（先講在前面）

1. **不要一次載入全部 7 份類型指南**——單份就 800–2,000 行，一次全塞會把上下文吃光。按類型讀一份。
2. **`godot --headless` 的 exit code 不可信**——出錯常常還是回傳 0。必須逐行掃 log 抓 `ERROR:`／`SCRIPT ERROR:`。
   這條寫在 `godot-verification-toolchain.md`，是整包裡最該先知道的一件事。

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
- **不含通用型 agent**（測試／UI 稽核／程式審查）：這三類不是 Godot 專屬所以未隨附。
  相關路由表已改成指向包內對應章節，**照章節走即可，不需要額外 agent**；你若已有這類 agent，派它時仍用包內的標準當尺
- **不含 Unreal 相關**（原始收藏中有，但與本包主題無關）
- `pixel-game-scene-pipeline` §4 的工具腳本**只有 3 支附程式碼**（`Scripts/`，已實測可跑）；
  其餘幾支高度綁定原專案（畫布尺寸、實測調色盤、特定 CLI 工具）只給行為契約，
  請照該節「要點」欄自行實作——那一欄才是踩過坑後定下來的部分

---

## 授權

本 repo 的**原創內容**（`SKILL.md`、`References/godot-*.md`、`agents/*.md`）可自由使用與修改。

`References/vendor/`、`References/vendor-sprite-forge/` 下是**第三方原文**，各有其授權，
其中 terma 的部分為 **CC-BY-SA-4.0（署名＋相同方式分享）**。
**再散布前請務必讀 [`NOTICE.md`](NOTICE.md)**，並保留各 vendor 目錄內的 LICENSE 檔。

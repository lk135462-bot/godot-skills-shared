---
name: godot-game-dev
description: 觸發條件：「Godot 開發」、「做一個 RPG / 塔防 / 平台跳躍 / Roguelike / 策略 / 4X / 視覺小說遊戲」、「遊戲類型指南」、「Godot 4 怎麼做 X 系統」、「像素風 Godot 專案」、「像素完美渲染 / pixel perfect」、「TileMapLayer / Parallax2D 怎麼用」。Godot 4 七大遊戲類型開發指南路由器，按遊戲類型載入對應完整指南（屬性系統、戰鬥、AI、存檔、UI 等該類型核心系統的 GDScript 4.x 實作模式），另含像素呈現橫切面指南（渲染設定、TileMapLayer、攝影機、光影、匯入匯出）。
---

# Godot 遊戲類型開發指南（godot-game-dev）

## 角色定位

七大遊戲類型的 Godot 4 開發指南入口。每份指南 800-2,000 行，涵蓋該類型核心系統的完整 GDScript 4.x 實作模式——**按類型載入，不要全部讀**。

## 類型路由表

| 遊戲類型 | 觸發情境 | 讀取指南 |
|---|---|---|
| **RPG** | 屬性系統、背包、任務追蹤、Buff/Debuff、裝備詞綴 | `References/godot-rpg-game.md` |
| **塔防** | 塔攻擊、波次、敵人路徑、抽卡塔防 | `References/godot-tower-defense.md` |
| **策略** | 回合制、大地圖、資源管理、勢力 AI | `References/godot-strategy-game.md` |
| **4X 策略** | 探索/擴張/開發/征服、科技樹、外交 | `References/godot-4x-strategy.md` |
| **平台跳躍** | 角色物理、跳躍手感、關卡設計 | `References/godot-platformer.md` |
| **Roguelike** | 程序生成、permadeath、隨機物品 | `References/godot-roguelike.md` |
| **視覺小說** | 對話系統、分支劇情、立繪管理 | `References/godot-visual-novel.md` |

### 橫切面指南（跨類型共用）

| 主題 | 觸發情境 | 讀取指南 |
|---|---|---|
| **像素呈現** | 渲染設定（stretch / snap）、TileMapLayer、攝影機、光影、匯入匯出 | `References/godot-pixel-art.md` |
| **架構紀律** | 通訊三律、場景組織、設計四件套、審查要點、除錯七步、熱路徑禁忌、專案設置 | `References/godot-architecture-discipline.md` |
| **資源檔安全** | 手寫/LLM 代寫 .tscn/.tres、instance 覆寫、序列化語法、validator | `References/godot-file-format-safety.md` |
| **驗證工具鏈** | headless 驗收（allow-list）、GUT/自製 harness、**無注入 runtime 測試（bridge autoload）**、Godot MCP 生態 | `References/godot-verification-toolchain.md` |

> 任何像素風專案開工必讀 `godot-pixel-art.md`，與類型指南**並用**（類型指南管系統架構，它管像素呈現層）。
> 上述三份橫切面為 2026-08 外部開源資源的吸收整合版（GodotPrompter／terma／godot_codex_skills），原始全文 vendor 於 `References/vendor/`（**授權條款與已知勘誤見 `vendor/LICENSES.md`，再散布前必讀**）；2D 光影全套、像素完美三件套、匯入症狀表、shader 配方庫等深水內容直接讀 `vendor/godotprompter/` 對應檔。

## 與其他資源的關係

- **AI 產圖場景管線**（整張生成 → 摳件 → 疊層方法論）→ `pixel-game-scene-pipeline` Skill（邊界：該 Skill 管美術產出與 AI 產圖方法論，本 Skill 管引擎系統實作）
- **像素藝術基本功 / AI 產圖工具** → `pixel-game-scene-pipeline` Skill 的 `References/`
- **遊戲設計**（機制 / 數值平衡）→ `game-designer` Agent
- **GDScript 實作** → `godot-gameplay-scripter` Agent
- **Shader / 特效** → `godot-shader-developer` Agent
- **關卡 / 敘事 / 音效** → `level-designer` / `narrative-designer` / `game-audio-engineer` Agent

## 認知框架（怎麼想）

- **類型決定架構**：先確認遊戲類型再讀對應指南，混型遊戲取多份指南的對應章節
- **指南是模式不是教條**：指南提供經過驗證的實作模式，專案具體需求優先
- **大型功能先設計再實作**：觸及 3+ 系統的功能先產出 `GAME_FLOW.md` 再動手（有 `game-designer` agent 就派它寫）

## 誠實邊界（做不到什麼）

- 指南基於 Godot 4.3–4.7 撰寫（2026-07 快照，現行 stable 4.7）；新版 API 變動需對照官方文件
- 不含美術資產製作（→ game-technical-artist / sprite-prompt-engineer）

## 反模式（不要這樣做）

- ❌ 一次載入全部 7 份指南（單份就 800-2,000 行）
- ❌ 跳過類型判斷直接寫 code（架構錯了重構成本極高）

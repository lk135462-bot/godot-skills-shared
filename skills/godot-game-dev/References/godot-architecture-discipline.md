# Godot 架構紀律（GodotPrompter 吸收版）

> 來源：jame581/GodotPrompter v1.13.2（MIT）完整精讀後的情境適配摘要，2026-08-18 整合。
> 原文全文在 `vendor/godotprompter/`；本檔每節末尾標出處。想看完整程式碼範例讀原文。
> 標 💡 者為實戰適配註記（與原文不同、或需補充之處）。

## 1. 通訊三律（最重要的一條）

- **signal 向上**：子節點對外只發 signal，不知道誰在聽
- **method call 向下**：父節點直接呼叫子節點方法
- **EventBus 橫向**：無父子關係的系統間事件走 autoload EventBus（typed signals）
- 禁 `get_parent()` 鏈、禁兄弟節點硬路徑 `get_node("../Sibling")`

💡 採「core 發 signal、表現層訂閱」的專案天然符合此律。三律真正的價值是**給了它名字**——review 時用這三個詞判違規，比「感覺耦合太深」可操作得多。
出處：`vendor/godotprompter/scene-organization.md`（通訊節）、`vendor/godotprompter/godot-code-review.md`（反模式 §1）

## 2. 場景組織

- **一場景一職責**：兩個詞內講不出場景名字＝做太多了
- 拆場景四條件：會複用／約 15+ 節點／可獨立測試／多人防衝突
- 組合 vs 繼承拇指法則：「整份複製只改幾個 export」→ 繼承；「想混搭子集」→ 組合
- 子節點按關注點分容器（Visuals／Collision／Components／AI）

出處：`vendor/godotprompter/scene-organization.md`

## 3. 設計先行流程（brainstorming 四步）

1. 一次只問一個釐清問題
2. 提 2-3 個架構選項附取捨，先講推薦
3. 逐節核可：場景樹 → signal map → 資料流
4. 產實作計畫，**每個 task 標註要載哪些 skill/參考**

**設計文件四件套**：場景樹 ASCII 圖＋節點職責表＋signal map（signal→來源→消費者→payload）＋資料流追蹤。
動手前 9 問精選：資料誰擁有？失敗模式是什麼？最小可行版本長怎樣？

💡 這套等同「設計先行」紀律的 Godot 特化版：觸及 3+ 系統的功能先出設計文件再動手，四件套即該文件的產物格式。
出處：`vendor/godotprompter/godot-brainstorming.md`（含「寶箱」五步規劃實例與 18 種需求→節點選型對照表；四件套完整成品版在原 repo references/example-chest.md，未 vendor）

## 4. 熱路徑三禁＋審查要點

- 禁 `_process` 內 `get_node()` → `@onready` 快取
- 禁熱路徑字串比較 → `&"StringName"`
- 禁熱路徑 `load()` → `preload`（編輯期已知路徑）／`load`（資料驅動）／`load_threaded_request`（大資源）
- signal 一律過去式命名（`died`、`reward_taken`）
- `queue_free()` 不用 `free()`

完整 8 區審查表＋bad/good 對照碼：`vendor/godotprompter/godot-code-review.md`（可作 review 標準包底稿）

## 5. 除錯七步法

Reproduce → Isolate（二分停用腳本／最小場景）→ **寫下假設**（防漂移）→ Trace → 修根因不修症狀 → Verify → **補回歸測試，以 bug 情境命名**。

💡 「以 bug 情境命名的回歸測試」（例如 `test_hit_pipeline`）即第七步的產物；「假設先寫下來」是七步裡最常被跳過的一步。
出處：`vendor/godotprompter/debugging-systematic-method.md`

## 6. 專案設置慣例

- `.godot/` 不進版控；**`*.import` sidecar 必須進版控**（Godot 4 官方慣例；原文由其 .gitattributes `*.import` 條目隱含而非明文——其 .gitignore 裡的 `.import/` 是 Godot 3 legacy 目錄，別讀反）；美術/音訊在 `.gitattributes` 標 binary
- 四大 Autoload 慣例：GameManager／EventBus／AudioManager／SaveManager（少量、職責明確）
- Input Map 優先，禁硬編碼按鍵
- 目錄兩法：split（資產/場景/腳本分離，利多人）vs co-located（按 feature 聚合，利獨立開發）

出處：`vendor/godotprompter/godot-project-setup.md`

## 7. 版本紀律（引用他們的做法時）

- 指南底線 Godot 4.3+；新版特性須經官方 class reference／migration guide 確認才可寫進知識庫
- ⚠ 已知原文勘誤：`vendor/godotprompter/2d-essentials.md` 把 TileMapLayer 標 4.5+、Parallax2D 標 4.4+——**兩者皆為 4.3 引入**（其自家其他檔案寫法正確；vendor/LICENSES.md 有記錄）

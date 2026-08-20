# Godot 驗證工具鏈（headless 驗收＋無注入 runtime 測試）

> 來源整合：biologicpro/godot_codex_skills（MIT）的 headless 驗收器＋terma godot-interactive（CC-BY-SA-4.0）的 runtime bridge＋GodotPrompter 測試紀律。2026-08-18。
> 原文：`vendor/godot-headless/run_headless_check.sh`、`vendor/terma-godot-interactive/`。

## 第一軌：headless 驗收鏈（每次改動必跑）

1. **語法**：`godot --headless --check-only --script <file.gd>`
2. **匯入**：`godot --headless --path . --import`（新增 `class_name`／素材後必跑，漏跑會出現「類別找不到」的假錯誤）
3. **啟動檢查**：`godot --headless --path . --quit`——專案能不能開
4. **場景 smoke test**：`--quit-after N`（跑 N 幀自動退出，預設 180）
5. **純邏輯測試**：自製 harness（`run_tests.gd` 模式）或 GUT `gut_cmdln.gd -gexit`——**只測 RefCounted/Resource 純邏輯，不測場景樹**

**驗收判定的關鍵設計**（來自 run_headless_check.sh，值得學的部分）：
- **exit 0 不代表過關**——Godot 出錯常仍回傳 0；必須逐行掃 log，任何 `ERROR:`／`SCRIPT ERROR:` 判 fail
- **allow-list 收編已知噪音**：可重複傳入 `--allow-error <樣式>` 放行預期錯誤（如缺 icon.svg），其餘一律紅
- 高頻跑動時隔離使用者資料目錄，防污染／撞檔

💡 原腳本是 bash ＋ macOS 偏向；Windows 直接用等價指令組合即可。**allow-list 思想才是重點**，搬用時自寫幾行 `grep -vE` 白名單即可。

## 第二軌：runtime bridge 無注入測試（Playwright 式）

**問題**：用 pydirectinput 等系統級鍵鼠注入測試遊戲，會與正在用電腦的真人搶輸入（實測發生過兩次，測試中途游標被搶走）。
**正解**：**file-based 指令協議**——遊戲內掛一個 bridge autoload，逐幀輪詢指令檔、執行、寫回應檔＋定期截圖。AI 迴圈：觀察截圖→查場景樹→下指令→再觀察。**全程不碰系統鍵鼠**。

terma 的 `godot_mcp_bridge.gd`（299 行，完整可搬：`vendor/terma-godot-interactive/godot_mcp_bridge.gd`）工具面：
- `run/stop`、`get_debug_output`——**這兩組在原方案屬 MCP server 端**（進程管理／stdout 擷取），bridge 本體不含；自建 harness 時由測試腳本自己 spawn 進程、收 stdout
- `game_screenshot`（定期自動截）
- `game_scene_tree`（含 Control 節點 rect/text/visible——找按鈕座標不用猜）
- `game_click`／`game_key`／`game_action`（在遊戲內合成 InputEvent，非系統注入）
- `game_get_property`／`game_set_property`（**強制遊戲狀態加速測試**——直接把 HP 設 10 測瀕死，不用真打）

💡 移植要點：
1. 原文用 `/tmp/godot_mcp_*.json` → Windows 改 `user://` 或專案旁目錄
2. 其 server 端 repo 是佔位符——**bridge autoload 本身就是全部價值**，不需要 MCP server：測試腳本直接讀寫指令檔即可（Python 端幾十行）
3. 掛載紀律：bridge 只在 debug build 掛（`OS.is_debug_build()` 守門），正式版不進
4. 導入效益：可取代 playtest bot 的系統級注入路線；場景樹查詢順帶取代像素偵測——按鈕 rect 直接拿，不用再從截圖量邊框

## MCP server 生態速查（要「AI 操作 Godot 編輯器」時）

- **Coding-Solo/godot-mcp**（5.2k star，MIT，npx 一行裝）：headless 型最大宗——run_project／get_debug_output／create_scene／add_node 等 14 tools；結構級編輯夠用
- runtime-bridge 型是生態缺口；上述 terma bridge 是唯一開源可搬實作
- 編輯器 plugin 型：ee0pdt 停更 17 個月、GDAI 閉源商業——不採
- ⚠ 網上「最佳 Godot MCP」比較文多出自競品（Summer Engine）行銷，可信度低——與 gh API 實查數據不符處以實查為準

> 生態盤點基於 2026-08 GitHub API 實查（star 數、最後 commit）；引用前請自行複查現況。

## 注入式 E2E 三陷阱（實戰以儀器化遙測逼出）

1. **file-based 橋的殘留指令**：橋接若開機即輪詢 cmd 檔，上一輪殘留的 `quit` 會讓遊戲啟動即自盡（且退出碼 0，極易誤判成「使用者關掉」）。橋接 `_ready` 必須先刪殘留 cmd/res 檔再開始輪詢。
2. **座標空間錯配**：`scene_tree` 回報的 Control rect 是設計解析度 canvas 座標；`Input.parse_input_event` 吃視窗座標。stretch（canvas_items）下兩者差一個縮放——注入前用 `get_viewport().get_final_transform() * pos` 映射，否則「按鈕點不到但不報錯」。
3. **輪詢滑鼠 vs 注入事件**：`get_global_mouse_position()`／`Viewport.get_mouse_position()` 反映 OS 實體游標，**吃不到 parse_input_event 注入的 motion**。症狀＝UI 按鈕可點（走事件 position）、但瞄準/朝向亂飛（走輪詢）。修法＝改事件驅動：`_input` 快取 `InputEventMouse.position`（視口座標），用時 `get_canvas_transform().affine_inverse() * cached` 還原世界座標——對實體滑鼠行為完全等價（同一公式、同一事件源），對注入可測。
- **診斷紀律**：連續失敗別堆理論——上儀器。逐發取樣「彈體位置/目標 HP/技能就緒」（0.08s 粒度）三行數據直接指出斷環（本例：ready 循環正常＋HP 不掉＋彈體反向＝瞄準源壞）。

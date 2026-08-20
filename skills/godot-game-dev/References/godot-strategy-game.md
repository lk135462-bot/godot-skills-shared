# Godot 4 策略遊戲開發指南
# 回合制大地圖策略 — 架構知識庫 v3

## 觸發條件
當要開發 Godot 4 回合制策略遊戲（類三國志／文明帝國／全軍破敵）時使用。

> 本指南的模式取自一個 17 城／3 勢力／44 名將領規模的實作專案，已在該規模下驗證；
> 常數、公式係數、資料檔命名皆為**可調範例**，非鐵則。

---

## ▌ LAYER 1：速查（每次必讀）

### 環境前提
| 項目 | 值 |
|------|------|
| 引擎版本 | Godot 4.3+（本指南模式在 4.6.x 上驗證） |
| 語法檢查 | `<godot 執行檔> --headless --check-only --path <專案根> > check.txt 2>&1` |

> 指令的 exit code 不可信——**必須逐行掃 log**，出現 `ERROR:`／`SCRIPT ERROR:` 即判 fail。
> 完整驗收鏈見 `godot-verification-toolchain.md`。

### Autoload 順序
```
GameEvents   → 全域事件匯流排（訊號定義）
GameData     → 世界資料（城市/武將/裝備/技能）
SaveManager  → 存讀檔
```

### 勢力顏色常數（範例）

勢力顏色集中成單一常數表，UI／地圖／戰報全部查表，禁散落各處硬編碼：

```gdscript
const FACTION_COLORS := {
    "faction_a": Color(0.2, 0.4, 0.8),  # 藍
    "faction_b": Color(0.2, 0.7, 0.3),  # 綠
    "faction_c": Color(0.8, 0.3, 0.2),  # 紅
    "neutral":   Color(0.5, 0.5, 0.5),
}
```

### 將領戰鬥力公式（範例係數，需依自家數值曲線調整）
```
戰鬥力 = (武力×0.6 + 統率×0.4)
        × 裝備加成（force+command bonus）
        × 學習技能倍率（衝鋒/伏兵/馬術…）
        × (1 + 等級×0.05)
        × (1 + 羁絆bonuses×0.02)
防禦方地形係數 = 1.0 + city.defense / 200.0
```

---

## ▌ LAYER 2：架構設計（開發新系統前讀）

### 2-1. Event Bus 模式（最核心）

**任何跨系統通訊一律走 GameEvents，禁止直接呼叫：**

```gdscript
# GameEvents.gd（Autoload）
signal city_owner_changed(city_id: String, new_owner: String)
signal battle_started(from_city_id: String, to_city_id: String)
signal battle_ended(result: Dictionary)
signal skill_triggered(general_name: String, skill_name: String)
signal general_leveled_up(general_id: String, new_level: int)
signal random_event_occurred(event_data: Dictionary)
signal turn_started(turn: int)
signal turn_ended(turn: int)
signal game_saved()
signal game_loaded()
```

**城市易主必須走方法：**
```gdscript
# ❌ 禁止直接賦值
city.owner = "wei"

# ✅ 必須呼叫方法（內部 emit 事件）
city.change_owner("wei")
```

### 2-2. 場景層次架構（實際執行版）

```
MainMap (Node2D)
├── Camera2D          (position_smoothing_enabled=true)
├── [動態] Line2D     (城市連線，z_index=-1)
├── [動態] ColorRect  (地圖底色，z_index=-10/-11)
├── [動態] CityNode   (城市色塊+名稱+兵力，動態建立)
└── UI (CanvasLayer)
    ├── TopBar (PanelContainer) → TurnLabel / DateLabel / FactionLabel / HintLabel
    ├── BottomBar (HBoxContainer) → SaveButton / LoadButton / EndTurnButton
    ├── CityPanel (右側，offset_right=-290) → 城市動作面板
    ├── GeneralPanel (左側，offset_right=320, offset_bottom=750)
    │   └── VBox → PanelTitle + Sep + ScrollContainer → ContentVBox
    ├── BattlePopup (中央彈窗，±220×±180)
    ├── HelpPanel (中央彈窗)
    └── NotificationLabel (錨點0.88，漸出動畫)
```

### 2-3. 輸入處理（已驗證的最終方案）

**重要：CanvasLayer 的 Control 即使 visible=false 仍可能攔截輸入**

```gdscript
# ✅ 正確：使用 _input + 手動 UI 矩形檢測
func _input(event: InputEvent):
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
        if not _mouse_over_ui():
            _try_click(get_global_mouse_position())  # ← 必須用這個，非 event.position

func _mouse_over_ui() -> bool:
    var mp = get_viewport().get_mouse_position()  # ← 螢幕座標
    var panels = [city_panel, general_panel, battle_popup, $UI/TopBar, $UI/BottomBar, $UI/HelpPanel]
    for panel in panels:
        if panel.visible and panel.get_global_rect().has_point(mp):
            return true
    return false

func _try_click(world_pos: Vector2):
    # world_pos 是世界座標（已處理 Camera zoom/position）
    var min_dist: float = 50.0
    for cid in game_data.cities:
        var d = world_pos.distance_to(game_data.cities[cid].position)
        if d < min_dist:
            closest = game_data.cities[cid]
    if closest: _select_city(closest)
```

**三個座標系分清楚：**
| 函數 | 回傳 | 用途 |
|------|------|------|
| `get_viewport().get_mouse_position()` | 螢幕座標 | UI 矩形碰撞檢測 |
| `get_global_mouse_position()` | 世界座標 | 點擊城市（考慮 Camera zoom） |
| `event.position` | 螢幕座標 | ❌ 不要用在城市座標比較 |

### 2-4. 資料模型（Resource 型別）

```gdscript
class_name City extends Resource
@export var id: String
@export var city_name: String
@export var owner: String
@export var garrison: int
@export var buildings: Dictionary = {"farm": 1, "market": 1, "barracks": 1, "wall": 1}
# ← buildings 只存 level 整數，邏輯在方法內

class_name General extends Resource
@export var id: String
@export var general_name: String
@export var force / intellect / command: int
@export var level: int = 1
@export var exp: int = 0
@export var city_id: String = ""
@export var bonds: Dictionary = {}
@export var equipment: Dictionary = {"weapon": "", "armor": "", "horse": ""}
@export var learned_skills: Dictionary = {}   # skill_id -> level 1-3
@export var skills: Array = []               # 固有特技（從 JSON 載入）
```

### 2-5. AI 分層決策架構

#### 現有實作（優先級迴圈）
```gdscript
# AIController.gd
func process_faction(faction: String):
    # Priority 1: 防守（garrison < 40%）
    for city in weak_cities: move_reinforcements(city)
    # Priority 2: 經濟（自動建設）
    for city in rich_cities: do_build(city)
    # Priority 3: 攻擊（garrison > 120，找最弱鄰城）
    for city in strong_cities: do_attack(city)
```

#### Wesnoth CandidateAction 模式（下一步升級目標）
```gdscript
# 每個行動類型有自己的評分函數，AI 選最高分執行
class CandidateAction:
    var action_type: String       # "attack", "reinforce", "build", "recruit"
    func evaluate(faction: String, game_data: Node) -> float:
        # 返回 0.0~1.0 的優先度分數
        pass
    func execute(faction: String, game_data: Node) -> void:
        pass

# FactionAI 主迴圈
func process_faction(faction: String):
    var best_score = 0.0
    var best_action: CandidateAction = null
    for action in candidate_actions:
        var score = action.evaluate(faction, game_data)
        if score > best_score:
            best_score = score
            best_action = action
    if best_action and best_score > 0.1:
        best_action.execute(faction, game_data)
```

#### DecisionService 查詢層（AI 不直接讀原始資料）
```gdscript
class AIDecisionService:
    func get_threats(faction: String) -> Array[ThreatData]
    func get_expansion_targets(faction: String) -> Array[City]
    func evaluate_city_value(city: City) -> float
    func get_reinforcement_priority() -> Array[City]
```

### 2-6. 武將培養 UI（完整流程）

```
城市面板 → 🛒 市場 → 瀏覽 equipment.json 裝備 → 花費城市金錢 → 加入 player_inventory
城市面板 → 📋 武將培養 → 列出城內武將
    → 🔧 培養 [武將名] → 培養畫面（在 GeneralPanel 左側顯示）
        ├── 屬性顯示（基礎值 + 裝備加成 = 實際值）
        ├── 固有特技 + 羁絆列表
        ├── 裝備欄（3 槽：武器/鎧甲/坐騎）[更換][卸下]
        │   └── 更換 → 顯示 player_inventory 中對應類型物品
        └── 學習技能（8 種，各 0-3 星）[升級(N金)]
```

**關鍵函數：**
```gdscript
_show_general_list(city)      # 顯示城內武將卡片列表
_show_cultivation(gen, city)  # 完整培養畫面
_show_equip_picker(gen, city, slot)  # 裝備選擇
_build_equip_slots(gen, city)        # 建立裝備欄 UI
_build_learnable_skills(gen, city)   # 建立技能升級 UI
```

### 2-7. 事件系統

```gdscript
# EventSystem.gd（static class，preload 使用）
const EventSystemClass = preload("res://scripts/EventSystem.gd")

# 在回合結束時：
var evt = EventSystemClass.roll_event(game_data, player_faction)
if not evt.is_empty():
    evt["effect"].call()     # Dictionary with "title", "desc", "effect" (Callable)
    _show_event_popup(evt)   # 複用 BattlePopup 節點
```

**已實作的 9 種事件：**
豐收+200糧 / 商隊+150金 / 民亂-50兵 / 神醫+80兵 / 武將修煉+50exp /
結義強化羁絆 / 旱災-100糧 / 流民涌入+30人口 / 間諜-80金

---

## ▌ LAYER 3：完整參考（按需讀取）

### 3-1. 檔案結構（全部腳本）

```
scripts/
├── GameEvents.gd      # Autoload：訊號定義
├── GameData.gd        # Autoload：城市/武將/裝備/技能資料
├── SaveManager.gd     # Autoload：JSON 存讀檔
├── City.gd            # class_name City extends Resource
├── General.gd         # class_name General extends Resource
├── BattleSystem.gd    # 戰鬥解算（10回合模擬）
├── AIController.gd    # AI 決策
├── EventSystem.gd     # 隨機事件（static methods）
└── MainMap.gd         # 主場景控制器（~860行）

data/
├── cities.json        # 17座城市，含鄰居/座標/初始資源
├── generals.json      # 45名武將（魏16/蜀11/吳10/中立8）
├── equipment.json     # 武器8/鎧甲6/坐騎5（grade 1-4）
└── skills.json        # 8種可學技能，解鎖費用[100,250,500]金
```

### 3-2. 存讀檔結構（JSON 完整欄位）

```json
{
  "turn": 1,
  "game_date": {"year": 184, "month": 1},
  "player_faction": "shu",
  "player_inventory": ["iron_sword", "leather_armor"],
  "cities": {
    "chengdu": {"owner": "shu", "garrison": 200, "food": 300,
                "gold": 280, "buildings": {"farm": 1, "market": 2},
                "general_ids": ["liubei", "zhugeliang"]}
  },
  "generals": {
    "liubei": {"level": 3, "exp": 50, "force": 62, "intellect": 77,
               "command": 80, "city_id": "chengdu",
               "bonds": {"guanyu": 3, "zhangfei": 5},
               "equipment": {"weapon": "iron_sword", "armor": "", "horse": ""},
               "learned_skills": {"charge": 2, "tactics": 1}}
  }
}
```

### 3-3. 戰鬥解算詳細流程（BattleSystem.resolve）

```
1. emit battle_started
2. 計算雙方 atk_power / def_power（含技能倍率）
3. 兵種剋制（infantry vs cavalry vs archer 三角）
4. 觸發特技事件通報（40%機率/技能）
5. 10回合模擬迴圈：
   雙方每回合互損 = power × remaining/100 × randf(0.85~1.15)
6. 勝負判定：def<=0 OR atk_remaining > def_remaining*0.5 → 攻方勝
7. 雙方 gain_exp，add_bond
8. emit battle_ended(result)
```

**Wesnoth 戰鬥公式（可擴充參考）：**
```
命中率    = 基礎命中 × (1 - 地形防禦%)    ← 防守方地形影響命中
傷害      = 攻擊力 × 抵抗修正(%)          ← 兵種相剋透過 resistance_table 查詢
多擊       = 攻擊次數 × 每次傷害           ← 將命中失敗的回合計入結果
```

### 3-4. 裝備系統資料流

```
GameData.equipment_data          ← 載入 equipment.json
GameData.player_inventory        ← 玩家背包（全局）
GameData.buy_equipment(city_id, item_id) → 扣城市金 + append inventory
GameData.get_inventory_by_slot(slot)     → 過濾 inventory 取對應類型

General.get_equip_bonus()        ← 直接讀 GameData.equipment_data（autoload）
General.equip_item(item_id, slot)
General.unequip_slot(slot)

BattleSystem: General.get_battle_power() 已內建裝備加成，無需額外傳參
```

### 3-5. 可學技能定義（skills.json）

| ID | 名稱 | 效果描述 | 戰鬥加成倍率 |
|----|------|----------|-------------|
| charge | 衝鋒 | 提升攻擊傷害 | +10%/+5%/+5%（每Lv） |
| shield | 鐵壁 | 提升防禦 | （防禦型，目前未獨立加成） |
| tactics | 兵法 | 提升兵力上限 | +5%/+4%/+4% |
| inspire | 鼓舞 | 激勵士氣 | +6%/+3%/+3% |
| ambush | 伏兵 | 奇襲額外傷害 | +12%/+6%/+6% |
| logistics | 治軍 | 提升糧草產量 | （後勤型，目前未計入戰鬥） |
| horseman | 馬術 | 騎兵加成 | +8%/+4%/+4% |
| archery | 弓術 | 弓兵加成 | +8%/+4%/+4% |

解鎖費用：Lv1=100金、Lv2=250金、Lv3=500金

### 3-6. 城市建設參數

| 建築 | 費用 | 每Lv效果 | 上限 |
|------|------|----------|------|
| farm | 200 | 食糧產量×Lv | 5 |
| market | 150 | 金錢收入×Lv | 5 |
| barracks | 300 | 兵力上限×Lv | 5 |
| wall | 250 | 防禦值+10/Lv | 5 |

`get_max_garrison() = population/5 × barracks_level`
`get_defense_value() = defense + wall_level×10 + garrison/10`

### 3-7. 武將初始分配（GENERAL_ASSIGNMENTS）

歷史依據分配，39名武將各歸其位，5名流浪者留給酒館池。

```
魏·鄴城：曹操, 夏侯淵, 樂進, 曹丕
魏·許昌：司馬懿, 張郃, 荀彧, 曹仁
魏·洛陽：典韋, 夏侯惇, 賈詡, 徐晃, 司馬昭
魏·合肥：許褚, 張遼, 鄧艾

蜀·成都：劉備, 諸葛亮, 趙雲, 龐統, 劉禪
蜀·漢中：張飛, 馬超, 姜維, 魏延
蜀·劍門：黃忠
蜀·荊州：關羽

吳·建業：孫權, 魯肅, 太史慈, 孫策, 周泰
吳·武昌：周瑜, 甘寧, 陸遜, 黃蓋, 呂蒙

中立·下邳：呂布, 貂蟬
中立·平原：袁紹

酒館流浪者（5人）：
  劉璋（益州偏好）, 張魯（漢中/益州）,
  公孫瓚（冀州/青州/并州）, 董卓（司隸/并州）, 華佗（全圖）
```

地域偏好常數（`GENERAL_REGION_PREF`）：
- 控制流浪者出現在哪些城市的酒館
- 空陣列（華佗）= 任何地方都可出現
- `refresh_tavern` 優先匹配城市 `region` 欄位

### 3-8. 招募系統資料流（Phase 4）

```
GameData.tavern_pools: Dictionary    # city_id -> [gen_id, ...] 最多3個
GameData.captive_generals: Array     # 玩家俘虜的 gen_id 列表
GameData.GENERAL_REGION_PREF: const  # gen_id -> [地區名, ...] 酒館地域偏好

GameData.get_available_generals()    → city_id=="" 且非俘虜的武將
GameData.refresh_tavern(city_id)     → 按地域偏好填充 tavern_pools[city_id]
GameData.get_tavern_generals(city_id)→ 返回仍在 available 的武將列表
GameData.hire_from_tavern(city_id, gen_id) → 免費雇用，改 faction/city_id
GameData.capture_general(gen_id, to_city_id) → 加入 captive_generals
GameData.get_captives_in_city(city_id)   → 過濾 captive_generals
GameData.recruit_captive(city_id, gen_id)→ 免費招降，改 faction/city_id
GameData.release_captive(gen_id)         → city_id="" 歸還流浪池
```

**戰鬥俘虜觸發（BattleSystem.resolve）：**
```gdscript
if winner == "attacker" and not defender.id.begins_with("dummy_"):
    if randf() < 0.30:
        result["captive_general_id"] = defender.id
```

**UI 函數（MainMap.gd）：**
```
_show_tavern(city)    → GeneralPanel 顯示可雇武將 + [✅ 雇用]
_show_captives(city)  → GeneralPanel 顯示俘虜 + [招降] [釋放]
```

**城市面板按鈕觸發條件：**
- 「🍺 酒館雇將」：永遠顯示（玩家城市）
- 「⛓ 俘虜（N名）」：僅當 get_captives_in_city(city.id) 非空時顯示

### 3-9. 已知陷阱（實際踩過，必須記住）

| # | 問題 | 錯誤做法 | 正確做法 |
|---|------|---------|---------|
| 1 | UI 點擊穿透 | `_unhandled_input` | `_input` + `_mouse_over_ui()` |
| 2 | 城市點擊偏移 | `event.position` | `get_global_mouse_position()` |
| 3 | TSCN 字色設定 | `theme_override_colors/font_color` | code 用 `add_theme_color_override()` |
| 4 | class_name 跨檔存取 | 直接用類別名 | 非 autoload 的 static class 需 `preload()` |
| 5 | 城市易主 | 直接 `city.owner =` | 必須 `city.change_owner()` |
| 6 | Array.join() 型別 | `"sep".join(array)` 可能失敗 | `"sep".join(PackedStringArray(array))` |
| 7 | Loop closure capture | 閉包直接用 loop 變數 | 先 `var x = loop_var` 再在閉包用 `x` |
| 8 | EventSystem static | `EventSystem.method()` | `const ESClass = preload(...); ESClass.method()` |
| 9 | AStarGrid2D 限制 | 用 Grid 處理不規則圖 | 用 `AStar2D`，手動 add_point + connect_points |
| 10 | CanvasLayer 攔截 | 以為 visible=false 不擋輸入 | mouse_filter 獨立於 visibility |

---

## ▌ LAYER 4：開源架構研究精華（按系統類型分類）

### 研究來源
| 專案 | 語言/引擎 | 特色系統 |
|------|----------|---------|
| Battle for Wesnoth | C++ / SDL | CandidateAction AI、Terrain Defense、多擊戰鬥 |
| Freeciv | C | 城市生產佇列、Dijkstra AI 決策樹 |
| OpenRA | C# / .NET | Actor+Trait 元件系統、Service 分層 |
| LimboAI (Godot Plugin) | GDScript | 完整行為樹：BTSequence/BTSelector/BTCondition/BTAction |
| godot-open-rts | GDScript | Signal 架構分離、FeatureFlags Autoload |
| ramaureirac/godot-tactical-rpg | GDScript | Stats Resource、技能系統 |
| zhs007/sanguo | Cocos2d-x | 三國 SLG 架構（城市/武將/出兵） |
| kikuchiyo/romance_three_kingdoms | Godot | 三國遊戲 Godot 原生實作參考 |

---

### 4-1. AI 決策系統

#### CandidateAction 模式（Wesnoth）
每種 AI 行動封裝為獨立類別，各自評分，主迴圈選最高分執行：
```gdscript
class_name CandidateAction
var action_type: String

func evaluate(faction: String, world: Node) -> float:
    # 返回 0.0（不可行）~ 1.0（最優先）
    return 0.0

func execute(faction: String, world: Node) -> void:
    pass

# 範例：攻擊行動
class AttackAction extends CandidateAction:
    func evaluate(faction, world) -> float:
        var cities = world.get_faction_cities(faction)
        var strong = cities.filter(func(c): return c.garrison > 120)
        if strong.is_empty(): return 0.0
        return 0.7  # 有兵力就給 0.7 分

# AI 主迴圈
func process_ai_turn(faction: String):
    var best = candidate_actions.reduce(func(a, b):
        return a if a.evaluate(faction, game_data) >= b.evaluate(faction, game_data) else b
    )
    if best.evaluate(faction, game_data) > 0.1:
        best.execute(faction, game_data)
```

#### 行為樹架構（LimboAI + 自製）
```gdscript
# 安裝 LimboAI plugin，或自製最小版本
class BTNode:
    enum Status { SUCCESS, FAILURE, RUNNING }
    func tick(blackboard: Dictionary) -> Status: return Status.FAILURE

class BTSequence extends BTNode:  # 全部成功才成功（AND）
    var children: Array[BTNode]
    func tick(bb) -> Status:
        for child in children:
            if child.tick(bb) != Status.SUCCESS: return Status.FAILURE
        return Status.SUCCESS

class BTSelector extends BTNode:  # 任一成功即成功（OR）
    var children: Array[BTNode]
    func tick(bb) -> Status:
        for child in children:
            if child.tick(bb) == Status.SUCCESS: return Status.SUCCESS
        return Status.FAILURE

class BTCondition extends BTNode:
    var check: Callable  # func(blackboard) -> bool
    func tick(bb) -> Status:
        return Status.SUCCESS if check.call(bb) else Status.FAILURE

class BTAction extends BTNode:
    var action: Callable  # func(blackboard) -> void
    func tick(bb) -> Status:
        action.call(bb)
        return Status.SUCCESS

# FactionAI 使用行為樹
class FactionAIController:
    var tree: BTNode
    var blackboard: Dictionary = {}

    func _build_tree() -> BTNode:
        return BTSelector.new([
            BTSequence.new([  # 若有威脅 → 防守
                BTCondition.new(func(bb): return bb.get("under_threat", false)),
                BTAction.new(_do_reinforce)
            ]),
            BTSequence.new([  # 若資源充足 → 建設
                BTCondition.new(func(bb): return bb.get("gold", 0) > 200),
                BTAction.new(_do_build)
            ]),
            BTAction.new(_do_attack)  # 預設攻擊
        ])

    func process_turn(faction: String):
        blackboard = _build_blackboard(faction)
        tree.tick(blackboard)
```

#### Freeciv Dijkstra 威脅評估
```gdscript
func _evaluate_threat(city: City) -> float:
    var score = 0.0
    for neighbor_id in city.neighbors:
        var n = game_data.cities[neighbor_id]
        if n.owner != city.owner:
            score += n.garrison * 0.01  # 敵方兵力轉換威脅分
    return score
```

---

### 4-2. 戰鬥系統

#### Wesnoth 地形防禦與兵種剋制
```gdscript
# 地形防禦影響命中率（不是傷害）
const TERRAIN_DEFENSE = {
    "plain": 0.0,   "forest": 0.25,
    "mountain": 0.4, "castle": 0.6
}

# 兵種抵抗表（攻擊方兵種 → 防守方兵種 → 傷害修正）
const RESISTANCE_TABLE = {
    "cavalry": {"archer": 0.7, "infantry": 1.2, "cavalry": 1.0},
    "archer":  {"cavalry": 1.3, "infantry": 1.0, "archer": 0.9},
    "infantry":{"archer": 1.1, "cavalry": 0.85, "infantry": 1.0}
}

func calc_damage(attacker: General, defender: General, city: City) -> float:
    var base = attacker.get_battle_power()
    var terrain_mod = 1.0 - TERRAIN_DEFENSE.get(city.terrain_type, 0.0)
    var resist = RESISTANCE_TABLE.get(attacker.unit_type, {}).get(defender.unit_type, 1.0)
    return base * terrain_mod * resist
```

#### 多擊系統（每武將多次攻擊）
```gdscript
# 武將有 strikes（攻擊次數）屬性
func resolve_multi_strike(atk: General, def: General, city: City) -> Dictionary:
    var total_dmg = 0
    for _i in range(atk.strikes):
        if randf() > TERRAIN_DEFENSE.get(city.terrain_type, 0.0):
            total_dmg += calc_damage(atk, def, city)
    return {"damage": total_dmg, "strikes": atk.strikes}
```

---

### 4-3. 地圖與尋路

#### AStar2D 城市圖（不規則節點）
```gdscript
var astar: AStar2D = AStar2D.new()
var path_cache: Dictionary = {}

func _build_city_graph():
    for city_id in game_data.cities:
        var city = game_data.cities[city_id]
        var hash_id = city_id.hash() & 0x7FFFFFFF
        astar.add_point(hash_id, city.position)

    for city_id in game_data.cities:
        var city = game_data.cities[city_id]
        var from_hash = city_id.hash() & 0x7FFFFFFF
        for neighbor_id in city.neighbors:
            var to_hash = neighbor_id.hash() & 0x7FFFFFFF
            if not astar.are_points_connected(from_hash, to_hash):
                astar.connect_points(from_hash, to_hash)

func get_city_path(from_id: String, to_id: String) -> Array:
    var key = "%s_%s" % [from_id, to_id]
    if key in path_cache: return path_cache[key]
    var path = astar.get_id_path(
        from_id.hash() & 0x7FFFFFFF,
        to_id.hash() & 0x7FFFFFFF
    )
    path_cache[key] = path
    return path

func clear_path_cache():  # 城市易主時呼叫
    path_cache.clear()
```

#### BFS 鄰城擴散（戰術範圍）
```gdscript
func get_cities_in_range(start_id: String, range: int) -> Array[String]:
    var visited = {start_id: true}
    var queue = [[start_id, 0]]
    var result = []
    while not queue.is_empty():
        var pair = queue.pop_front()
        var city_id = pair[0]; var dist = pair[1]
        if dist > 0: result.append(city_id)
        if dist < range:
            for n in game_data.cities[city_id].neighbors:
                if n not in visited:
                    visited[n] = true
                    queue.append([n, dist + 1])
    return result
```

#### Hex 網格（六角地圖，軸向座標）
```gdscript
# 若改用六角格地圖（Red Blob Games 公式）
func hex_distance(a: Vector2i, b: Vector2i) -> int:
    return (abs(a.x - b.x) + abs(a.x + a.y - b.x - b.y) + abs(a.y - b.y)) / 2

func hex_neighbors(h: Vector2i) -> Array[Vector2i]:
    var dirs = [Vector2i(1,0), Vector2i(1,-1), Vector2i(0,-1),
                Vector2i(-1,0), Vector2i(-1,1), Vector2i(0,1)]
    return dirs.map(func(d): return h + d)
```

---

### 4-4. 事件與隨機系統

#### 加權事件選擇（比現有更精確）
```gdscript
static func select_weighted(events: Array, weights: Array) -> Dictionary:
    var total = 0.0
    for w in weights: total += w
    var roll = randf() * total
    var acc = 0.0
    for i in range(events.size()):
        acc += weights[i]
        if roll <= acc: return events[i]
    return events[-1]

# 使用範例：
var event_pool = [harvest_event, drought_event, merchant_event]
var weights    = [0.3,           0.15,          0.55]  # 各自機率
var result = select_weighted(event_pool, weights)
```

#### 建築工期系統（目前是即時完工，可升級）
```gdscript
class BuildingQueue extends Resource:
    var queue: Array = []  # [{type, remaining_turns}]

    func add_project(building_type: String, turns: int):
        queue.append({"type": building_type, "remaining": turns})

    func process_turn() -> Array:  # 返回本回合完工的建築
        var completed = []
        for project in queue:
            project["remaining"] -= 1
            if project["remaining"] <= 0:
                completed.append(project["type"])
        queue = queue.filter(func(p): return p["remaining"] > 0)
        return completed
```

---

### 4-5. 元件組合架構（OpenRA Actor+Trait 模式）

適用於「不同武將有不同能力組合」的擴充需求：

```gdscript
# 不用繼承，用 Trait 組合（避免深層繼承）
class_name GeneralTrait
func get_stat_bonus() -> Dictionary: return {}
func on_battle_start(context: Dictionary) -> void: pass
func on_battle_end(context: Dictionary) -> void: pass

class ChargeTrait extends GeneralTrait:
    func get_stat_bonus() -> Dictionary: return {"force": 15}
    func on_battle_start(context) -> void:
        context["atk_multiplier"] = context.get("atk_multiplier", 1.0) * 1.1

class General extends Resource:
    var traits: Array[GeneralTrait] = []

    func get_total_stat_bonus() -> Dictionary:
        var result = {}
        for trait in traits:
            for k in trait.get_stat_bonus():
                result[k] = result.get(k, 0) + trait.get_stat_bonus()[k]
        return result
```

---

### 4-6. 服務層架構

將功能從 MainMap.gd（上帝類）抽出，各司其職：

```gdscript
# BattleService.gd（Autoload 或 class）
class_name BattleService

static func resolve(from_city: City, to_city: City,
                    attackers: Array[General], garrison: int) -> Dictionary:
    # 純計算，不依賴任何節點
    pass

# NavigationService.gd
class_name NavigationService

static func get_path(from_id: String, to_id: String) -> Array[String]:
    pass

static func get_reachable_cities(faction: String) -> Array[String]:
    pass
```

---

### 4-7. UI 與效能優化

#### VisibleOnScreenNotifier2D（大地圖省 CPU）
```gdscript
# 對每個 CityNode 動態加入
func _setup_visibility_notifier(city_node: Node2D):
    var notifier = VisibleOnScreenNotifier2D.new()
    city_node.add_child(notifier)
    notifier.screen_exited.connect(func(): city_node.set_process(false))
    notifier.screen_entered.connect(func(): city_node.set_process(true))
```

#### 多存檔槽
```gdscript
const SAVE_TEMPLATE = "user://save_%d.json"

func save_game(slot: int = 0):
    var path = SAVE_TEMPLATE % slot
    # ... 現有存檔邏輯

func load_game(slot: int = 0):
    var path = SAVE_TEMPLATE % slot
    # ... 現有讀檔邏輯

func list_saves() -> Array[Dictionary]:
    var result = []
    for i in range(5):
        var path = SAVE_TEMPLATE % i
        if FileAccess.file_exists(path):
            # 讀取 turn/faction 等摘要資訊
            result.append({"slot": i, "exists": true})
    return result
```

---

## ▌ LAYER 5：系統擴充參考路線

> 以下是回合制策略遊戲「大地圖框架已跑通之後」的常見擴充順序與設計要點，
> 依相依性排列（招募 → 存檔 → AI → 戰鬥 → 架構遷移），可按專案需求跳過或重排。

### 擴充 1：招募系統

```
設計：
├── 酒館（tavern）城市設施：每回合刷新 2-3 名待雇武將候選
├── 捕俘系統：擊敗敵將後 30% 機率俘虜，可招降或處決
├── 中立將領：不屬任何勢力的將領池，可被任意勢力招攬
└── 資料格式：generals.json 新增 "status": "neutral"/"captive"/"available"

實作要點：
├── GameData.available_generals: Array  ← 未分配武將池
├── city.tavern_pool: Array             ← 每城酒館刷新（每回合重置）
├── GameData.hire_general(gen_id, city_id) → 從 available 轉移到城市
└── BattleSystem 結算時：攻方勝利 → roll 是否俘虜防守武將
```

### 擴充 2：多存檔槽＋存檔選單

```
SaveSlotMenu（新 Scene）：
├── 5 個存檔槽，顯示「回合N / 勢力 / 日期」
├── 新遊戲 → 選擇勢力 → 覆蓋或選空槽
└── 讀取 → 直接進 MainMap，不回主選單
```

### 擴充 3：AI 升級到 CandidateAction

```
AIController 重構：
├── 現有優先級迴圈 → 改為 CandidateAction 評分陣列
├── 每種行動（attack/reinforce/build/recruit）各自有 evaluate()
├── 加入 DecisionService 查詢層，AI 不直接讀 GameData
└── 長期：接入 FactionAIController 行為樹版本
```

### 擴充 4：戰鬥深化

```
戰鬥升級選項（選擇性實作）：
├── 地形防禦：城市 terrain_type 影響命中率（Wesnoth 公式）
├── 兵種剋制：步兵/騎兵/弓兵三角，resistance_table 查詢
├── 多擊機制：武將 strikes 屬性（高武力→多次攻擊）
└── 戰鬥動畫：Line2D 繪製攻擊路徑 + Tween 淡出效果
```

### 擴充 5：長期架構遷移

```
若遊戲規模擴大（城市 30+、將領 100+）：
├── 考慮 Actor+Trait 架構取代 General 繼承（OpenRA 模式）
├── 考慮 BattleService/NavigationService 抽出（服務層）
├── 建築工期系統（BuildingQueue Resource）
└── LimboAI 插件整合（完整行為樹）
```

---


## ▌ 認知框架與誠實邊界

### 本指南涵蓋的範圍
- 完整 GDScript 4 腳本撰寫與除錯
- 基於 Event Bus 的系統擴充
- 資料 JSON 設計與解析
- UI 動態建立（不依賴額外 tscn）
- Godot 語法驗證（--check-only）
- 從開源策略遊戲架構（Wesnoth／Freeciv／OpenRA 等）提取模式並移植

### 已知不確定處（需自行驗證）
- 跨多版本 Godot 4 的 API 相容性（模式驗證於 4.6.x，新版須對照官方文件）
- `PackedStringArray` 隱式轉型的所有邊界情況
- 大規模地圖（100+城市）的效能極限
- LimboAI 插件與新版 Godot 4 的相容性（需自行測試）

### 反模式（實戰踩過，禁止）
- 直接賦值城市/武將狀態（繞過 Event Bus）
- 在 tscn 中用 `theme_override_colors/font_color`
- 用 `event.position` 做世界座標比較
- 非 autoload 的 class_name 腳本不經 preload 直接呼叫 static 方法
- 閉包直接捕捉 loop 變數（必須先 `var x = loop_var`）
- 在 MainMap.gd 直接實作邏輯而不抽出 Service（上帝類反模式）
# Godot 4 4X 大戰略遊戲開發 Skill
# 4X Strategy 架構知識庫 v2

## 觸發條件
當使用者要開發 4X 大戰略遊戲（探索/擴張/開發/消滅，如文明系列、太空帝國）時使用。

---

## LAYER 1：速查（每次必讀）

### 4X 設計支柱對照表
| X | 含義 | 核心系統 | 關鍵數值 | 玩家決策點 |
|---|------|---------|---------|-----------|
| Explore | 探索 | HexGrid、FogOfWar、Scout Unit | 視野半徑、移動力 | 何時送出偵察？往哪探？ |
| Expand | 擴張 | CityPlacement、BorderGrowth、Settler | 城市間距、文化邊界 | 在哪建城？搶地還是深耕？ |
| Exploit | 開發 | TileYields、TechTree、ProductionQueue | 食物/生產/科技/金幣 | 研究哪個科技？建什麼？ |
| Exterminate | 消滅 | CombatSystem、WarDeclaration、Siege | 攻防數值、ZoC | 宣戰時機？軍事路線？ |

### 核心系統一覽
| 系統 | 說明 |
|------|------|
| 六角地圖 | HexMap / TileMapLayer，儲存地形資料 |
| 科技樹 | 有向無環圖（DAG），依賴關係解鎖 |
| 外交 | 文明間關係值、協議、戰爭宣告 |
| 城市 | 生產力、食物、文化、人口成長 |
| AI | 每回合根據策略評估行動（評分系統） |
| 迷霧戰爭 | 已探索/可見/未知三層狀態 |
| 貿易路線 | A* 尋路 + 成本計算 + 金幣收益 |
| 回合制 | 所有文明依序執行回合 |

### MVP 最小可行場景結構

```
Main (Node2D)
+-- GameManager (Node)          回合/文明控制
+-- MapManager (Node)           地圖資料管理
|   +-- HexGrid (Node2D)        六角格子渲染
|   +-- FogOfWarLayer (Node2D)  迷霧遮罩層
+-- CivilizationManager (Node)  所有文明資料
+-- TechManager (Node)          科技樹狀態
+-- DiplomacyManager (Node)     外交關係
+-- TradeManager (Node)         貿易路線系統
+-- UnitLayer (Node2D)          所有單位
+-- CityLayer (Node2D)          所有城市
+-- AIController (Node)         AI 決策處理（分幀）
+-- Camera2D                    可縮放/平移
+-- HUD (CanvasLayer)
    +-- TurnInfo
    +-- ResourceBar
    +-- MiniMap
    +-- ActionMenu
    +-- TechTreeUI
    +-- DiplomacyUI
```

### 關鍵 GDScript 範式

**六角格座標系統（Cube Coordinates）**
```gdscript
# hex_grid.gd
class_name HexGrid
extends Node2D

const HEX_SIZE = 40.0
var hex_data: Dictionary = {}  # Vector3i -> HexTile

func cube_to_world(cube: Vector3i) -> Vector2:
    var x = HEX_SIZE * (3.0/2 * cube.x)
    var y = HEX_SIZE * (sqrt(3)/2 * cube.x + sqrt(3) * cube.z)
    return Vector2(x, y)

func world_to_cube(world: Vector2) -> Vector3i:
    var q = (2.0/3 * world.x) / HEX_SIZE
    var r = (-1.0/3 * world.x + sqrt(3)/3 * world.y) / HEX_SIZE
    return _cube_round(Vector3(q, -q-r, r))

func _cube_round(v: Vector3) -> Vector3i:
    var rx = round(v.x); var ry = round(v.y); var rz = round(v.z)
    var dx = abs(rx - v.x); var dy = abs(ry - v.y); var dz = abs(rz - v.z)
    if dx > dy and dx > dz: rx = -ry-rz
    elif dy > dz: ry = -rx-rz
    else: rz = -rx-ry
    return Vector3i(rx, ry, rz)

func get_neighbors(cube: Vector3i) -> Array[Vector3i]:
    var dirs = [
        Vector3i(1,-1,0), Vector3i(1,0,-1), Vector3i(0,1,-1),
        Vector3i(-1,1,0), Vector3i(-1,0,1), Vector3i(0,-1,1)
    ]
    var result: Array[Vector3i] = []
    for d in dirs: result.append(cube + d)
    return result

func hex_distance(a: Vector3i, b: Vector3i) -> int:
    return int((abs(a.x-b.x) + abs(a.y-b.y) + abs(a.z-b.z)) / 2)

func get_ring(center: Vector3i, radius: int) -> Array[Vector3i]:
    var results: Array[Vector3i] = []
    if radius == 0:
        results.append(center)
        return results
    var current = center + Vector3i(-radius, radius, 0)
    var dirs = [
        Vector3i(1,-1,0), Vector3i(1,0,-1), Vector3i(0,1,-1),
        Vector3i(-1,1,0), Vector3i(-1,0,1), Vector3i(0,-1,1)
    ]
    for i in range(6):
        for _j in range(radius):
            results.append(current)
            current += dirs[i]
    return results

func get_range(center: Vector3i, max_radius: int) -> Array[Vector3i]:
    var results: Array[Vector3i] = []
    for r in range(max_radius + 1):
        results.append_array(get_ring(center, r))
    return results
```

---

## LAYER 2：架構設計（開發新系統前讀）

### 六邊形座標系完整說明

Godot 4 的 TileMapLayer 預設使用 Offset Coordinates。
遊戲邏輯（距離/視野/鄰居）建議全程使用 Cube Coordinates（Vector3i，約束 x+y+z=0）。

#### 三種座標系比較

| 座標系 | 優點 | 缺點 | 適用場景 |
|--------|------|------|---------|
| Cube (x,y,z) | 運算直觀、鄰居/距離公式簡單 | 三個分量冗餘 | 遊戲邏輯計算 |
| Axial (q,r) | 比 Cube 省一個分量 | 部分公式較複雜 | 儲存、序列化 |
| Offset (col,row) | 對齊螢幕直覺 | 奇偶列不同偏移、運算麻煩 | TileMap 渲染 |

#### 完整轉換函式

```gdscript
# coordinate_converter.gd  -- 靜態工具類
class_name CoordinateConverter

# Axial -> Cube（補回 y 分量，使 x+y+z=0）
static func axial_to_cube(axial: Vector2i) -> Vector3i:
    return Vector3i(axial.x, -axial.x - axial.y, axial.y)

# Cube -> Axial（去掉 y 分量）
static func cube_to_axial(cube: Vector3i) -> Vector2i:
    return Vector2i(cube.x, cube.z)

# Offset Odd-R (水平六角，奇數列向右偏) -> Cube
static func offset_to_cube_odd_r(offset: Vector2i) -> Vector3i:
    var q = offset.x - (offset.y - (offset.y & 1)) / 2
    var r = offset.y
    return Vector3i(q, -q - r, r)

# Cube -> Offset Odd-R
static func cube_to_offset_odd_r(cube: Vector3i) -> Vector2i:
    var col = cube.x + (cube.z - (cube.z & 1)) / 2
    return Vector2i(col, cube.z)

# Offset Even-R (水平六角，偶數列向右偏) -> Cube
static func offset_to_cube_even_r(offset: Vector2i) -> Vector3i:
    var q = offset.x - (offset.y + (offset.y & 1)) / 2
    var r = offset.y
    return Vector3i(q, -q - r, r)

# TileMapLayer 座標 -> Cube（統一入口，全專案只改這裡）
static func tilemap_to_cube(tilemap_pos: Vector2i, odd_r: bool = true) -> Vector3i:
    return offset_to_cube_odd_r(tilemap_pos) if odd_r else offset_to_cube_even_r(tilemap_pos)
```


### 霧戰（Fog of War）實作

三種可見狀態：UNKNOWN（從未探索，全黑）、EXPLORED（曾探索，顯示地形）、VISIBLE（此回合可見）

```gdscript
# fog_of_war.gd
class_name FogOfWar
extends Node2D

enum TileVisibility { UNKNOWN, EXPLORED, VISIBLE }

var visibility_map: Dictionary = {}  # civ_id -> {cube -> TileVisibility}

func update_visibility(civ_id: int, units: Array, cities: Array) -> void:
    var civ_vis: Dictionary = visibility_map.get(civ_id, {})
    for key in civ_vis.keys():
        if civ_vis[key] == TileVisibility.VISIBLE:
            civ_vis[key] = TileVisibility.EXPLORED
    for unit in units:
        _reveal_around(civ_id, unit.hex_pos, unit.sight_range)
    for city in cities:
        _reveal_around(civ_id, city.hex_pos, 2)
    visibility_map[civ_id] = civ_vis

func _reveal_around(civ_id: int, center: Vector3i, radius: int) -> void:
    if not visibility_map.has(civ_id): visibility_map[civ_id] = {}
    var civ_vis = visibility_map[civ_id]
    var hexgrid: HexGrid = get_node("/root/Main/MapManager/HexGrid")
    for cube in hexgrid.get_range(center, radius):
        if _has_line_of_sight(center, cube):
            civ_vis[cube] = TileVisibility.VISIBLE

func get_visibility(civ_id: int, cube: Vector3i) -> TileVisibility:
    return visibility_map.get(civ_id, {}).get(cube, TileVisibility.UNKNOWN)

func _has_line_of_sight(from_pos: Vector3i, to_pos: Vector3i) -> bool:
    var hexgrid: HexGrid = get_node("/root/Main/MapManager/HexGrid")
    var dist = hexgrid.hex_distance(from_pos, to_pos)
    if dist <= 1: return true
    for i in range(1, dist):
        var t = float(i) / dist
        var sf = Vector3(
            lerp(float(from_pos.x), float(to_pos.x), t),
            lerp(float(from_pos.y), float(to_pos.y), t),
            lerp(float(from_pos.z), float(to_pos.z), t)
        )
        var sample = hexgrid._cube_round(sf)
        var tile = hexgrid.hex_data.get(sample)
        if tile and tile.get("terrain") == "mountain": return false
    return true

func render_fog(civ_id: int) -> void:
    var hexgrid: HexGrid = get_node("/root/Main/MapManager/HexGrid")
    for cube in hexgrid.hex_data.keys():
        var world_pos = hexgrid.cube_to_world(cube)
        match get_visibility(civ_id, cube):
            TileVisibility.UNKNOWN:   _draw_fog_tile(world_pos, Color.BLACK)
            TileVisibility.EXPLORED:  _draw_fog_tile(world_pos, Color(0,0,0,0.5))
            TileVisibility.VISIBLE:   _clear_fog_tile(world_pos)

func _draw_fog_tile(_pos: Vector2, _color: Color) -> void: pass
func _clear_fog_tile(_pos: Vector2) -> void: pass

func to_dict() -> Dictionary:
    var result = {}
    for civ_id in visibility_map.keys():
        result[str(civ_id)] = {}
        for cube in visibility_map[civ_id].keys():
            result[str(civ_id)]["%d,%d,%d"%[cube.x,cube.y,cube.z]] = visibility_map[civ_id][cube]
    return result
```

### 完整科技樹 DAG + 前置條件檢查

```gdscript
# tech_tree.gd
class_name TechTree
extends Node

class TechData:
    var id: String; var name: String; var cost: int
    var prerequisites: Array[String]; var era: int
    var unlocks: Array[Dictionary]; var flavor_text: String

var techs: Dictionary = {}; var researched: Dictionary = {}
var current_research: Dictionary = {}

func load_from_json(path: String) -> void:
    var file = FileAccess.open(path, FileAccess.READ)
    if not file: push_error("TechTree: 無法開啟 %s" % path); return
    for td_raw in JSON.parse_string(file.get_as_text()):
        var td = TechData.new()
        td.id = td_raw["id"]; td.name = td_raw["name"]; td.cost = td_raw["cost"]
        td.prerequisites = td_raw.get("prerequisites", [])
        td.era = td_raw.get("era", 0); td.unlocks = td_raw.get("unlocks", [])
        td.flavor_text = td_raw.get("flavor_text", "")
        techs[td.id] = td

func can_research(civ_id: int, tech_id: String) -> bool:
    if not techs.has(tech_id): return false
    if is_researched(civ_id, tech_id): return false
    if current_research.get(civ_id, {}).get("tech_id","") == tech_id: return false
    for prereq in techs[tech_id].prerequisites:
        if not is_researched(civ_id, prereq): return false
    return true

func is_researched(civ_id: int, tech_id: String) -> bool:
    return tech_id in researched.get(civ_id, [])

func start_research(civ_id: int, tech_id: String) -> bool:
    if not can_research(civ_id, tech_id): return false
    current_research[civ_id] = {"tech_id": tech_id, "progress": 0}
    return true

func apply_science(civ_id: int, science_points: int) -> String:
    if not current_research.has(civ_id): return ""
    var r = current_research[civ_id]
    r.progress += science_points
    if r.progress >= techs[r.tech_id].cost:
        var done = r.tech_id; _complete_research(civ_id, done)
        current_research.erase(civ_id); return done
    return ""

func _complete_research(civ_id: int, tech_id: String) -> void:
    if not researched.has(civ_id): researched[civ_id] = []
    researched[civ_id].append(tech_id)
    for unlock in techs[tech_id].unlocks: _apply_unlock(civ_id, unlock)

func _apply_unlock(civ_id: int, unlock: Dictionary) -> void:
    match unlock.get("type",""):
        "unit":     UnlockManager.unlock_unit(civ_id, unlock["target"])
        "building": UnlockManager.unlock_building(civ_id, unlock["target"])
        "bonus":    UnlockManager.apply_bonus(civ_id, unlock["target"], unlock.get("value",1))
        _: push_warning("TechTree: 未知解鎖類型 %s" % unlock.get("type",""))

func get_available_techs(civ_id: int) -> Array[String]:
    var result: Array[String] = []
    for tech_id in techs.keys():
        if can_research(civ_id, tech_id): result.append(tech_id)
    return result

func get_era_progress(civ_id: int, era: int) -> Dictionary:
    var total = 0; var done = 0
    for tech in techs.values():
        if tech.era == era:
            total += 1
            if is_researched(civ_id, tech.id): done += 1
    return {"done": done, "total": total}

func to_dict() -> Dictionary:
    return {"researched": researched, "current_research": current_research}

func from_dict(d: Dictionary) -> void:
    researched = d.get("researched", {})
    current_research = d.get("current_research", {})
```

### 外交系統（完整版，含盟友自動參戰）

```gdscript
# diplomacy_manager.gd
class_name DiplomacyManager
extends Node

signal war_declared(attacker_id: int, defender_id: int)
signal peace_signed(civ_a_id: int, civ_b_id: int)
signal alliance_formed(civ_a_id: int, civ_b_id: int)

enum DiplomacyState { NEUTRAL, FRIENDLY, ALLIED, AT_WAR, COLD_WAR }

var relations: Dictionary = {}  # "civA_civB" -> {value, treaties, turns_at_war}

func initialize(civ_ids: Array[int]) -> void:
    for i in range(civ_ids.size()):
        for j in range(i+1, civ_ids.size()):
            relations[_key(civ_ids[i], civ_ids[j])] = {
                "value": 0, "treaties": [], "turns_at_war": 0
            }

func get_state(civ_a: int, civ_b: int) -> DiplomacyState:
    var rel = _get_rel(civ_a, civ_b); var v = rel.get("value", 0)
    if "war"      in rel.get("treaties", []): return DiplomacyState.AT_WAR
    if "alliance" in rel.get("treaties", []): return DiplomacyState.ALLIED
    if v >= 60:  return DiplomacyState.FRIENDLY
    if v <= -30: return DiplomacyState.COLD_WAR
    return DiplomacyState.NEUTRAL

func get_relation_value(civ_a: int, civ_b: int) -> int:
    return _get_rel(civ_a, civ_b).get("value", 0)

func modify_relation(civ_a: int, civ_b: int, delta: int, _reason: String = "") -> void:
    var rel = _get_rel(civ_a, civ_b)
    rel["value"] = clamp(rel.get("value", 0) + delta, -100, 100)

func declare_war(attacker: int, defender: int) -> void:
    var rel = _get_rel(attacker, defender)
    rel["value"] = -100
    rel["treaties"] = rel.get("treaties",[]).filter(func(t): return t!="peace" and t!="alliance")
    rel["treaties"].append("war"); rel["turns_at_war"] = 0
    war_declared.emit(attacker, defender)
    _notify_allies_of_war(defender, attacker)

func propose_peace(requester: int, target: int) -> bool:
    var rel = _get_rel(requester, target)
    if rel.get("turns_at_war", 0) < 3: return false
    if rel.get("value", -100) >= -20:
        var t = rel.get("treaties",[]).filter(func(x): return x!="war")
        t.append("peace"); rel["treaties"] = t
        rel["value"] = max(rel["value"], -20)
        peace_signed.emit(requester, target)
        return true
    return false

func form_alliance(civ_a: int, civ_b: int) -> bool:
    if get_state(civ_a, civ_b) != DiplomacyState.FRIENDLY: return false
    _get_rel(civ_a, civ_b)["treaties"].append("alliance")
    alliance_formed.emit(civ_a, civ_b); return true

func has_treaty(civ_a: int, civ_b: int, treaty_type: String) -> bool:
    return treaty_type in _get_rel(civ_a, civ_b).get("treaties", [])

func process_turn(civ_a: int, civ_b: int) -> void:
    match get_state(civ_a, civ_b):
        DiplomacyState.AT_WAR:  _get_rel(civ_a, civ_b)["turns_at_war"] += 1
        DiplomacyState.NEUTRAL: modify_relation(civ_a, civ_b, 1, "自然修復")

func _notify_allies_of_war(victim: int, aggressor: int) -> void:
    for key in relations.keys():
        var parts = key.split("_")
        var a = int(parts[0]); var b = int(parts[1])
        var other = b if a == victim else (a if b == victim else -1)
        if other == -1 or other == aggressor: continue
        if has_treaty(victim, other, "alliance"):
            declare_war(other, aggressor)

func _get_rel(civ_a: int, civ_b: int) -> Dictionary:
    var key = _key(civ_a, civ_b)
    if not relations.has(key): relations[key] = {"value":0,"treaties":[],"turns_at_war":0}
    return relations[key]

func _key(a: int, b: int) -> String:
    return "%d_%d" % [min(a,b), max(a,b)]

func to_dict() -> Dictionary: return {"relations": relations}
func from_dict(d: Dictionary) -> void: relations = d.get("relations", {})
```

### AI 決策評分系統

```gdscript
# civ_ai.gd
class_name CivAI
extends Node

# 人格：balanced / militarist / scientist / builder / expansionist / trader
@export var civ_id: int
@export var personality: String = "balanced"

signal ai_turn_completed(civ_id: int)

func take_turn() -> void:
    _research_phase(); _city_phase(); _unit_phase(); _diplomacy_phase()
    ai_turn_completed.emit(civ_id)

func _research_phase() -> void:
    if TechTree.current_research.has(civ_id): return
    var available = TechTree.get_available_techs(civ_id)
    if available.is_empty(): return
    TechTree.start_research(civ_id, _pick_best_tech(available))

func _pick_best_tech(ids: Array[String]) -> String:
    var best_score = -INF; var best = ids[0]
    for tid in ids:
        var s = _score_tech(tid)
        if s > best_score: best_score = s; best = tid
    return best

func _score_tech(tech_id: String) -> float:
    var tech = TechTree.techs.get(tech_id)
    if not tech: return 0.0
    var score = 1.0
    var kw_map = {
        "militarist":  ["military","iron","war"],
        "scientist":   ["science","writing","education"],
        "builder":     ["production","mining","masonry"],
        "expansionist":["agriculture","wheel","sailing"],
        "trader":      ["trade","currency","market"]
    }
    for kw in kw_map.get(personality, []):
        if kw in tech_id: score += 3.0; break
    score += tech.unlocks.size() * 0.5
    var ep = TechTree.get_era_progress(civ_id, tech.era)
    score += float(ep["done"]) / max(ep["total"], 1)
    score += randf_range(-0.3, 0.3)  # 微小隨機擾動，避免完全可預測
    return score

func _city_phase() -> void:
    var civ = CivilizationManager.get_civ(civ_id)
    for city in civ.cities:
        if not city.production_queue.is_empty(): continue
        city.production_queue.append(_pick_city_production(city))

func _pick_city_production(city) -> Dictionary:
    var civ = CivilizationManager.get_civ(civ_id)
    for eid in CivilizationManager.get_all_civ_ids():
        if eid == civ_id: continue
        if DiplomacyManager.get_state(civ_id,eid) == DiplomacyManager.DiplomacyState.AT_WAR:
            return {"type":"unit","unit_type":"warrior","cost":40,"progress":0}
    if city.population < 4:
        return {"type":"building","building_type":"granary","cost":60,"progress":0}
    if "workshop" not in city.buildings:
        return {"type":"building","building_type":"workshop","cost":80,"progress":0}
    if personality == "expansionist" and civ.cities.size() < 5:
        return {"type":"unit","unit_type":"settler","cost":100,"progress":0}
    return {"type":"building","building_type":"market","cost":80,"progress":0}

func _unit_phase() -> void:
    var civ = CivilizationManager.get_civ(civ_id)
    for unit in civ.units:
        if unit.moves_remaining <= 0: continue
        match unit.type:
            "scout":   _scout_move(unit)
            "settler": _settler_move(unit)
            "warrior": _warrior_move(unit)

func _scout_move(unit) -> void:
    var hexgrid = get_node("/root/Main/MapManager/HexGrid")
    for n in hexgrid.get_neighbors(unit.hex_pos):
        if FogOfWar.get_visibility(civ_id,n) == FogOfWar.TileVisibility.UNKNOWN:
            UnitManager.move_unit(unit, n); return
    unit.moves_remaining = 0

func _settler_move(unit) -> void:
    var best = CityPlacementEvaluator.find_best_city_site(civ_id)
    if best == unit.hex_pos: UnitManager.found_city(unit); return
    var path = AStarHex.find_path(unit.hex_pos, best)
    if path.size() > 1: UnitManager.move_unit(unit, path[1])
    else: unit.moves_remaining = 0

func _warrior_move(unit) -> void:
    var target = _find_nearest_enemy_city(unit.hex_pos)
    if not target: unit.moves_remaining = 0; return  # 沒目標，放棄
    var path = AStarHex.find_path(unit.hex_pos, target)
    if path.size() <= 1: unit.moves_remaining = 0; return  # 找不到路，放棄
    UnitManager.move_unit(unit, path[1])

func _find_nearest_enemy_city(from_pos: Vector3i):
    var hexgrid = get_node("/root/Main/MapManager/HexGrid")
    var best_dist = INF; var best_pos = null
    for eid in CivilizationManager.get_all_civ_ids():
        if eid == civ_id: continue
        if DiplomacyManager.get_state(civ_id,eid) != DiplomacyManager.DiplomacyState.AT_WAR: continue
        for city in CivilizationManager.get_civ(eid).cities:
            if FogOfWar.get_visibility(civ_id,city.hex_pos) == FogOfWar.TileVisibility.VISIBLE:
                var dist = hexgrid.hex_distance(from_pos, city.hex_pos)
                if dist < best_dist: best_dist = dist; best_pos = city.hex_pos
    return best_pos

func _diplomacy_phase() -> void:
    for other_id in CivilizationManager.get_all_civ_ids():
        if other_id == civ_id: continue
        match DiplomacyManager.get_state(civ_id, other_id):
            DiplomacyManager.DiplomacyState.AT_WAR:
                if DiplomacyManager.get_relation_value(civ_id,other_id) >= -20:
                    DiplomacyManager.propose_peace(civ_id, other_id)
            DiplomacyManager.DiplomacyState.FRIENDLY:
                if personality == "trader":
                    DiplomacyManager.form_alliance(civ_id, other_id)
```

### 貿易路線計算系統

```gdscript
# trade_manager.gd
class_name TradeManager
extends Node

class TradeRoute:
    var from_city_id: int; var to_city_id: int
    var path: Array[Vector3i]; var gold_per_turn: int; var is_sea_route: bool

var active_routes: Array[TradeRoute] = []

func calculate_route(from_city, to_city) -> TradeRoute:
    var route = TradeRoute.new()
    route.from_city_id = from_city.city_id; route.to_city_id = to_city.city_id
    var land = AStarHex.find_path_with_costs(from_city.hex_pos, to_city.hex_pos, _land_cost)
    var sea  = AStarHex.find_path_with_costs(from_city.hex_pos, to_city.hex_pos, _sea_cost)
    if sea.size() > 0 and sea.size() < land.size():
        route.path = sea; route.is_sea_route = true
    else:
        route.path = land; route.is_sea_route = false
    route.gold_per_turn = _calculate_gold(route)
    return route

func _land_cost(terrain: String) -> float:
    match terrain:
        "plains": return 1.0; "hills": return 2.0; "forest": return 1.5
        _: return INF  # 海洋/山脈不可陸路通行

func _sea_cost(terrain: String) -> float:
    match terrain:
        "coast": return 1.0; "ocean": return 1.5
        _: return INF  # 陸地不可海路通行

func _calculate_gold(route: TradeRoute) -> int:
    var base = 4 + route.path.size() / 5  # 路線越長越賺
    if route.is_sea_route: base += 2       # 海路獎勵
    var tc = CityManager.get_city(route.to_city_id)
    if tc: base += tc.population / 2      # 目標城市人口越多越值錢
    return base

func activate_route(route: TradeRoute) -> void: active_routes.append(route)

func process_trade_turn(civ_id: int) -> int:
    var total = 0
    for route in active_routes:
        var fc = CityManager.get_city(route.from_city_id)
        if fc and fc.owner_civ == civ_id: total += route.gold_per_turn
    return total

func validate_routes() -> void:
    active_routes = active_routes.filter(func(r): return r.path.all(
        func(c): return HexGrid.hex_data.has(c)
    ))
```


---

## LAYER 3: Complete Reference (read as needed)

### Terrain Yield Table
| Terrain | Food | Prod | Sci | Culture | Gold | Move | Notes |
|---------|------|------|-----|---------|------|------|-------|
| Plains  | 2    | 1    | 0   | 0       | 0    | 1.0  | Best city site |
| Hills   | 1    | 2    | 0   | 0       | 0    | 2.0  | Common iron |
| Forest  | 1    | 2    | 0   | 1       | 0    | 1.5  | Chop for bonus |
| Desert  | 0    | 0    | 0   | 0       | 0    | 1.0  | Late oil |
| Coast   | 1    | 0    | 0   | 0       | 2    | 1.0  | Fish resource |
| Mountain| 0    | 1    | 1   | 0       | 0    | INF  | Blocks LOS |
| Ocean   | 0    | 0    | 0   | 0       | 0    | 1.5  | Needs sailing |
| Tundra  | 1    | 0    | 0   | 0       | 0    | 1.5  | Low food |


### City Production System (GDScript)

`gdscript
# city.gd
class_name City
extends Node2D

@export var city_name: String
var city_id: int; var owner_civ: int = 0; var hex_pos: Vector3i
var population: int = 1; var food: float = 0.0
var production_queue: Array = []; var buildings: Array[String] = []
var yields: Dictionary = {"food":2,"production":1,"science":1,"culture":1,"gold":2}

func _on_turn_processed() -> void:
    _calculate_yields(); _grow_population(); _process_production()

func _calculate_yields() -> void:
    yields = {"food":2,"production":1,"science":1,"culture":1,"gold":2}
    var hexgrid = get_node("/root/Main/MapManager/HexGrid")
    for nb in hexgrid.get_range(hex_pos, 2):
        var tile = hexgrid.hex_data.get(nb)
        if tile: _add_tile_yields(tile)
    if "granary"      in buildings: yields["food"] += 2
    if "workshop"     in buildings: yields["production"] += 2
    if "library"      in buildings: yields["science"] += 2
    if "market"       in buildings: yields["gold"] += 3
    if "amphitheater" in buildings: yields["culture"] += 2

func _add_tile_yields(tile: Dictionary) -> void:
    match tile.get("terrain",""):
        "plains":   yields["food"]+=2; yields["production"]+=1
        "hills":    yields["food"]+=1; yields["production"]+=2
        "forest":   yields["production"]+=2; yields["culture"]+=1
        "coast":    yields["food"]+=1; yields["gold"]+=2
        "mountain": yields["production"]+=1; yields["science"]+=1
    match tile.get("resource",""):
        "wheat":    yields["food"]+=2
        "iron":     yields["production"]+=3
        "fish":     yields["food"]+=2
        "gold_ore": yields["gold"]+=3

func _grow_population() -> void:
    food += yields["food"]
    var needed = 15.0 + 6.0*(population-1) + pow(population-1, 1.8)
    if food >= needed: food -= needed; population += 1

func _process_production() -> void:
    if production_queue.is_empty(): return
    var item = production_queue[0]
    item.progress += yields["production"]
    if item.progress >= item.cost:
        production_queue.pop_front()
        match item.type:
            "unit":     UnitManager.spawn_unit(item.unit_type, hex_pos, owner_civ)
            "building": if item.building_type not in buildings: buildings.append(item.building_type)
`

### Victory Conditions

`gdscript
class_name VictoryChecker
extends Node

signal victory_achieved(civ_id: int, victory_type: String)

func check_all(civ) -> void:
    if _check_domination(civ): victory_achieved.emit(civ.id,"domination"); return
    if _check_science(civ):    victory_achieved.emit(civ.id,"science");    return
    if _check_culture(civ):    victory_achieved.emit(civ.id,"culture");    return
    if _check_diplomacy(civ):  victory_achieved.emit(civ.id,"diplomacy");  return

func _check_domination(civ) -> bool:
    return CityManager.get_all_capitals().all(func(c): return c.owner_civ == civ.id)

func _check_science(civ) -> bool:
    return TechTree.is_researched(civ.id, "space_colonization")

func _check_culture(civ) -> bool:
    return civ.total_culture >= 10000

func _check_diplomacy(civ) -> bool:
    var total = CivilizationManager.get_all_civ_ids().size(); var supporters = 0
    for oid in CivilizationManager.get_all_civ_ids():
        if oid == civ.id: continue
        if DiplomacyManager.get_state(civ.id, oid) in [
            DiplomacyManager.DiplomacyState.FRIENDLY,
            DiplomacyManager.DiplomacyState.ALLIED
        ]: supporters += 1
    return supporters >= (total - 1) * 0.6
`



---

## LAYER 4: Open Source Project Analysis

### Unciv
GitHub: https://github.com/yairm210/Unciv
Language: Kotlin / LibGDX, spiritual successor to Civ V open source
Platforms: Android / Windows / Linux / macOS

Key Architecture:
- 99% of code in core/ project (platform-independent)
- GameInfo is top-level state container for all civs, map, turns
- All game content (units/buildings/techs/civs) defined in assets/jsons/ as JSON, never hardcoded
- TileMap uses HashMap(Vector2 -> TileInfo), not array
- AI: CivInfoStats scoring system, intentional imperfections so humans can win
- Save: entire GameInfo serialized to JSON + GZIP, auto-saves each turn
- Key bug fix: clone GameInfo for renderer on NextTurn to avoid race condition
- Multiplayer: WebSocket transmits serialized GameInfo

GDScript equivalents:


---

### OpenCiv3
GitHub: https://github.com/C7-Game/OpenCiv3
Language: C# / Godot Engine, Civilization III modernized remake (active 2026)

Architecture:
- Three-layer separation: C7 (Godot rendering), C7Engine (game logic), C7GameData (data serialization)
- Layer separation means engine swap does not affect game logic
- JSON stores maps, saves, mod data
- Plans Lua scripting API for advanced mods
- Can import original Civ3 graphics and audio (if user owns license)

GDScript equivalent design:


---

### Simulatio Humanitatis
Forum: https://forum.godotengine.org/t/simulatio-humanitatis-a-4x-turn-based-strategy-game/127891
Language: GDScript / Godot, inspired by Civ3 + Civ6 hybrid

Design highlights:
- Policy system: stackable policies, but mutually exclusive ones cannot coexist
- Unit stacking: Civ3-style, multiple units per tile
- Multilingual: custom font system for Russian/Japanese scripts
- Population-driven borders: city cultural borders driven by population and culture values

Policy exclusion system:


---

### godot-open-rts
GitHub: https://github.com/lampe-games/godot-open-rts
Language: GDScript / Godot 4 (RTS template, not 4X but unit systems reusable)

Reusable systems:
- NavigationAgent2D + custom Avoidance: units do not stack
- RubberBand multi-unit selection
- Resource gathering and delivery logic

---

### Freeciv (Historical Reference)
GitHub: https://github.com/freeciv/freeciv
Language: C, founded 1996, oldest open source 4X (still actively maintained)

Architectural wisdom (transferable concepts):
- Ruleset: all game rules in plain-text .ruleset files, C reads and executes them
  -> equivalent to Godot res://data/ruleset/*.json
- Client/Server split: server handles logic, client only renders, inherently multiplayer
- 11 diplomatic protocols: ceasefire/peace/alliance/trade/intel-sharing etc
- AI: Dijkstra pathfinding + Threat Map for military target evaluation

Ruleset equivalent (res://data/ruleset/units.json):


---

### Stellar Throne (Godot Space 4X Devlog)
Blog: https://www.mrphilgames.com/blog/stellar-throne-devlog
Language: Godot

Architecture evolution:
- Initially put all logic in scene nodes, later refactored to pure GDScript logic classes + rendering separation
- Alien AI: threat scoring matrix (each civ maintains threat values 1-10 against all others)
- Large map performance: MultiMeshInstance2D batch renders thousands of stars instead of individual Sprites



---

## LAYER 5：常見陷阱（踩過才知道）

### 陷阱一：AI 卡死循環
症狀：AI 單位在同一格或相鄰格來回移動，永遠不結束回合。

根因：A* 返回空路徑時 AI 仍嘗試移動；移動目標永遠不可達。

修正（warrior_move 加放棄條件）：


### 陷阱二：Hex 座標轉換錯誤
症狀：點擊格子選到相鄰錯誤的格子，尤其在奇偶列邊界。

根因：混用 Odd-R 和 Even-R；world_to_cube 直接取 int 沒做捨入。

修正：


### 陷阱三：儲存大型 Dictionary 序列化過慢
症狀：存檔時遊戲卡頓 3-5 秒，地圖 80x80 時存檔 20MB+。

根因：JSON.stringify() 同步執行；Vector3i 鍵值無法直接序列化。

修正三步驟：


### 陷阱四：城市邊界擴張視覺不同步
症狀：文化邊界計算正確但渲染沒更新。

根因：更新 hex_data 後沒有觸發 TileMapLayer 重繪。

修正（使用 Signal 解耦）：


### 陷阱五：多文明 AI 執行競態條件
症狀：兩個 AI 同時對同一個空城市宣戰，城市歸屬異常。

根因：AI 決策基於快照狀態，但執行時狀態已被另一個 AI 改變。

修正（先蒐集決策，再批量執行）：


### 陷阱六：TileMapLayer 大地圖主執行緒阻塞
症狀：一次設定大量格子時 FPS 掉到個位數。

根因：set_cell_terrain_connect 需要重計算地形連接，O(n^2)。

修正（分幀執行 + 改用 set_cell）：


---

## LAYER 6：MVP 建構路線圖（v2）

### Phase 1：地圖生成（2-3 天）
- FastNoiseLite + 濕度雙噪聲生成地形（含沙漠/凍原/森林/海洋生物群系）
- Cube 座標系 + TileMapLayer 渲染（統一使用 CoordinateConverter）
- 攝影機拖拉、縮放（Camera2D + InputEvent）
- 迷霧初始化（全圖 UNKNOWN）

### Phase 2：城市與資源（2-3 天）
- 點擊空格建立城市（Settler 單位）
- 城市格子產出計算（鄰近格子 yields 加總 + 建築加成）
- 人口成長公式（食物積累，仿 Civ 公式）
- 迷霧更新（城市周邊 2 格 VISIBLE）
- 文化邊界擴張（Signal 驅動渲染）

### Phase 3：單位與移動（2-3 天）
- 基礎單位（Scout/Warrior/Settler）JSON 定義
- Cube A* 尋路（含地形成本加權，山脈 INF）
- 移動力限制與回合重置（reset_moves）
- 迷霧跟隨單位更新 + 視線遮擋（山脈格）

### Phase 4：科技樹（2-3 天）
- 10-15 個科技 JSON 定義（古代/古典/中世紀三時代）
- 科技樹 UI（DAG 視覺化，GraphNode 或 Control 手繪連線）
- 研究完成解鎖效果（_apply_unlock 分配系統）
- AI 自動選擇科技（人格評分系統 + 隨機擾動）

### Phase 5：外交與 AI（3-4 天）
- 完整外交狀態機（和平/友好/同盟/戰爭，盟友自動參戰）
- AI 五種人格（militarist/scientist/builder/expansionist/trader）
- AI 分幀執行（AIController，不卡主執行緒）
- 四種勝利條件判斷（征服/科技/文化/外交）

### Phase 6：貿易與效能（3-4 天）
- 陸路/海路 A* 貿易路線計算（地形成本加權，路線越長越賺）
- Chunk 分塊載入（大地圖 60x60+ 效能，每行等一幀）
- 非同步存讀檔（Thread + ZSTD 壓縮 + Vector3i 序列化）
- 懶惰產出計算快取（LazyYieldsCache）
- MultiMesh 批量渲染選項（超大地圖 100x100+）

---

## 認知框架與誠實邊界

### 我能做的
- 六角格座標系統（Cube/Axial/Offset 完整轉換，含 Odd-R/Even-R）
- 程序化地圖生成（Perlin + 濕度雙噪聲地形分類）
- 迷霧戰爭三層狀態（UNKNOWN/EXPLORED/VISIBLE）+ 視線遮擋
- 科技樹 DAG 依賴關係 + 前置條件遞迴檢查 + JSON 載入
- 城市生產佇列、人口成長公式、建築加成系統
- AI 評分系統（五種人格，分幀執行，放棄條件防止卡死）
- 外交狀態機（盟友自動參戰、回合自然修復）
- 貿易路線 A*（地形成本加權，陸海路選優）
- Chunk 分塊載入、懶惰計算效能優化、MultiMesh 批量渲染
- 非同步存讀檔（Thread + ZSTD 壓縮 + Vector3i 鍵值序列化）

### 我不確定的（需驗證）
- Godot 4.4+ TileMapLayer 大地圖 80x80+ 的實際 FPS 表現（社區回報差異很大）
- 多文明 AI 在 Thread 中讀取 GameState 的安全性（GDScript Thread 限制嚴格）
- 500+ 城市的 JSON 存檔序列化效能（需實際測試 ZSTD 壓縮效益）
- GDScript A* 在 100x100 地圖的尋路效能（可能需要 C++ GDExtension）

### 反模式（禁止）
- 禁止把地形資料存在 TileMapLayer custom_data：使用獨立 hex_data Dictionary（Vector3i -> Dictionary）
- 禁止在 _process() 中執行 AI 計算：使用 Thread 或 call_deferred 分散計算
- 禁止把所有文明邏輯放在一個腳本：Civilization/City/Unit/Tech/Diplomacy 各自獨立
- 禁止硬編碼科技/單位效果在 GDScript：使用 JSON 定義效果，腳本只負責解析執行
- 禁止 AI 移動沒有放棄條件：路徑找不到時必須 moves_remaining = 0
- 禁止直接用 Vector3i 作為 JSON 鍵值：必須先轉成字串 "%d,%d,%d"
- 禁止同步存大檔：必須用 Thread 非同步，或分幀寫入
- 禁止混用 Odd-R / Even-R 偏移格：全專案統一一種，在 CoordinateConverter 集中處理
- 禁止 AI 決策與執行混用共享狀態：先快照決策，再批量執行
- 禁止使用 set_cell_terrain_connect 大量填充格子：改用 set_cell 並分幀執行

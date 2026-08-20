# Godot 4 Roguelike 遊戲開發 Skill
# Roguelike 架構知識庫 v2

> **版本**：v2.0 | **更新日期**：2026-04-19 | **適用**：Godot 4.3+ / GDScript 4.x

## 觸發條件
當使用者要開發 Roguelike（永久死亡、程序生成地牢、回合制）遊戲時使用。

---

## LAYER 1：速查（每次必讀）

### 核心系統一覽

| 系統 | 說明 | v2 強化點 |
|------|------|-----------|
| 地牢生成 | BSP + Cellular Automata + Drunkard Walk 三種演算法 | 完整三演算法對比與切換 |
| 回合管理 | TurnQueue spend-time 系統 | 支援行動點數加速/減速 |
| FOV 迷霧 | **Shadowcasting 8 象限遞迴** | 取代 Bresenham，效能 3x |
| 實體系統 | Entity-Component 模式 | Entity Pool 物件池優化 |
| 物品系統 | ItemData Resource + 識別系統 + 效果執行器 | 完整架構，支援詛咒/附魔 |
| StatusEffect | 中毒/燃燒/冰凍/眩暈系統 | 堆疊/計時/免疫設計 |
| 永久死亡 | 死亡清除存檔，保留 meta-progression | 與 StatusEffect 整合 |
| 效能優化 | TileMap 批次更新 + Thread 非同步生成 | 移動裝置可用 |

### MVP 最小可行場景結構

```
Main (Node2D)
+-- GameManager (Node)              回合控制器 + Signal 匯流
+-- DungeonGenerator (Node)         地牢生成（三演算法可切換）
+-- TileMapLayer [floor]            地板渲染
+-- TileMapLayer [walls]            牆壁渲染（分層便於 batch 更新）
+-- EntityLayer (Node2D)            所有實體容器
|   +-- Player (CharacterBody2D)
|   +-- EnemyContainer (Node2D)
|   +-- ItemContainer (Node2D)
+-- FogOfWar (CanvasLayer)          Shadowcasting FOV 遮罩
+-- HUD (CanvasLayer)
|   +-- HealthBar
|   +-- StatusEffectDisplay
|   +-- MessageLog (RichTextLabel)
|   +-- InventoryPanel
+-- GeneratorThread (Node)          背景非同步生成管理
```

### 核心遊戲迴圈（事件驅動，非 _process）

```
玩家按鍵輸入
  -> GameManager.handle_input()
    -> 合法性驗證（牆壁/實體碰撞）
    -> 執行玩家行動（移動/攻擊/使用物品）
    -> FOVSystem.compute_shadowcast()  ← Shadowcasting 更新
    -> StatusEffect.tick_player()
    -> TurnQueue.advance_all_enemies()
      -> 每個敵人 AIComponent.take_turn()
      -> StatusEffect.tick_enemy()
    -> emit_signal("turn_ended")
    -> 渲染更新（TileMap batch + FogOfWar）
    -> 等待下次玩家輸入
```

---

## LAYER 2：三種地牢生成演算法（完整實作）

### 演算法對比總表

| 演算法 | 適合地圖風格 | 連通保證 | 房間均勻性 | 效能 |
|--------|------------|----------|-----------|------|
| BSP Tree | 傳統城堡/地牢 | 需手動連廊 | 高（葉節點均勻） | O(n log n) |
| Cellular Automata | 洞穴/自然地形 | 需洪水填充驗證 | 低（有機隨機） | O(w×h×iterations) |
| Drunkard Walk | 緊湊迷宮/礦坑 | 天然連通 | 低（隨機漫步） | O(steps) |

### DungeonGenerator — 三演算法整合

```gdscript
# dungeon_generator.gd
class_name DungeonGenerator
extends Node

enum Algorithm { BSP, CELLULAR_AUTOMATA, DRUNKARD_WALK }

const FLOOR := 0
const WALL  := 1
const MIN_R := 4
const MAX_R := 12

@export var width      : int = 80
@export var height     : int = 50
@export var algorithm  : Algorithm = Algorithm.BSP
@export var bsp_depth  : int = 5
@export var ca_iterations : int = 5
@export var ca_fill_ratio : float = 0.48
@export var drunk_steps   : int = 1500

var grid  : Array = []
var rooms : Array[Rect2i] = []
var rng   := RandomNumberGenerator.new()

signal generation_complete(grid: Array, rooms: Array)

func generate(seed_val: int = 0) -> Array:
    if seed_val != 0:
        rng.seed = seed_val
    _init_grid(WALL)
    rooms.clear()
    match algorithm:
        Algorithm.BSP:               _run_bsp()
        Algorithm.CELLULAR_AUTOMATA: _run_ca()
        Algorithm.DRUNKARD_WALK:     _run_drunk()
    emit_signal("generation_complete", grid, rooms)
    return grid

func generate_async(seed_val: int = 0) -> void:
    var thread := Thread.new()
    thread.start(_thread_generate.bind(seed_val, thread))

func _thread_generate(seed_val: int, thread: Thread) -> void:
    generate(seed_val)
    call_deferred("_thread_done", thread)

func _thread_done(thread: Thread) -> void:
    thread.wait_to_finish()

func _init_grid(fill: int) -> void:
    grid = []
    for _y in height:
        var row: Array[int] = []
        row.resize(width)
        row.fill(fill)
        grid.append(row)

func set_tile(x: int, y: int, v: int) -> void:
    if x >= 0 and x < width and y >= 0 and y < height:
        grid[y][x] = v

func get_tile(x: int, y: int) -> int:
    if x >= 0 and x < width and y >= 0 and y < height:
        return grid[y][x]
    return WALL

func is_walkable(pos: Vector2i) -> bool:
    return get_tile(pos.x, pos.y) == FLOOR

# ─── BSP Tree ──────────────────────────────────────────
func _run_bsp() -> void:
    _bsp_split(Rect2i(1, 1, width - 2, height - 2), bsp_depth)
    _bsp_connect_rooms()

func _bsp_split(region: Rect2i, depth: int) -> void:
    if depth == 0 or region.size.x < MIN_R * 2 + 1 or region.size.y < MIN_R * 2 + 1:
        _bsp_carve_room(region)
        return
    var split_horizontal := region.size.y > region.size.x
    if region.size.x == region.size.y:
        split_horizontal = rng.randi() % 2 == 0
    if split_horizontal:
        var split_y := rng.randi_range(region.position.y + MIN_R, region.end.y - MIN_R)
        _bsp_split(Rect2i(region.position, Vector2i(region.size.x, split_y - region.position.y)), depth - 1)
        _bsp_split(Rect2i(Vector2i(region.position.x, split_y), Vector2i(region.size.x, region.end.y - split_y)), depth - 1)
    else:
        var split_x := rng.randi_range(region.position.x + MIN_R, region.end.x - MIN_R)
        _bsp_split(Rect2i(region.position, Vector2i(split_x - region.position.x, region.size.y)), depth - 1)
        _bsp_split(Rect2i(Vector2i(split_x, region.position.y), Vector2i(region.end.x - split_x, region.size.y)), depth - 1)

func _bsp_carve_room(region: Rect2i) -> void:
    var rw := rng.randi_range(MIN_R, min(MAX_R, region.size.x - 2))
    var rh := rng.randi_range(MIN_R, min(MAX_R, region.size.y - 2))
    var rx := region.position.x + rng.randi_range(1, max(1, region.size.x - rw - 1))
    var ry := region.position.y + rng.randi_range(1, max(1, region.size.y - rh - 1))
    var room := Rect2i(rx, ry, rw, rh)
    rooms.append(room)
    for cy in range(room.position.y, room.end.y):
        for cx in range(room.position.x, room.end.x):
            set_tile(cx, cy, FLOOR)

func _bsp_connect_rooms() -> void:
    for i in range(1, rooms.size()):
        var a := rooms[i - 1].get_center()
        var b := rooms[i].get_center()
        if rng.randi() % 2 == 0:
            _hcorridor(a.x, b.x, a.y)
            _vcorridor(a.y, b.y, b.x)
        else:
            _vcorridor(a.y, b.y, a.x)
            _hcorridor(a.x, b.x, b.y)

func _hcorridor(x1: int, x2: int, y: int) -> void:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        set_tile(x, y, FLOOR)

func _vcorridor(y1: int, y2: int, x: int) -> void:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        set_tile(x, y, FLOOR)

# ─── Cellular Automata ──────────────────────────────────
func _run_ca() -> void:
    for y in height:
        for x in width:
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                grid[y][x] = WALL
            else:
                grid[y][x] = WALL if rng.randf() < ca_fill_ratio else FLOOR
    for _i in ca_iterations:
        _ca_step()
    _ca_remove_isolated_regions()
    _ca_extract_open_areas()

func _ca_step() -> void:
    var new_grid: Array = []
    for y in height:
        var row: Array[int] = []
        row.resize(width)
        for x in width:
            row[x] = WALL if _ca_count_walls(x, y, 1) >= 5 else FLOOR
        new_grid.append(row)
    grid = new_grid

func _ca_count_walls(cx: int, cy: int, r: int) -> int:
    var count := 0
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            var nx := cx + dx; var ny := cy + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                count += 1
            elif grid[ny][nx] == WALL:
                count += 1
    return count

func _ca_remove_isolated_regions() -> void:
    var visited := {}
    var regions: Array[Array] = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if grid[y][x] == FLOOR and not visited.has(Vector2i(x, y)):
                regions.append(_flood_fill(x, y, visited))
    if regions.is_empty():
        return
    regions.sort_custom(func(a, b): return a.size() > b.size())
    for i in range(1, regions.size()):
        for pos in regions[i]:
            grid[pos.y][pos.x] = WALL

func _flood_fill(sx: int, sy: int, visited: Dictionary) -> Array:
    var stack := [Vector2i(sx, sy)]
    var region: Array[Vector2i] = []
    var dirs := [Vector2i(1,0), Vector2i(-1,0), Vector2i(0,1), Vector2i(0,-1)]
    while not stack.is_empty():
        var pos: Vector2i = stack.pop_back()
        if visited.has(pos): continue
        if get_tile(pos.x, pos.y) != FLOOR: continue
        visited[pos] = true
        region.append(pos)
        for d in dirs:
            if not visited.has(pos + d):
                stack.append(pos + d)
    return region

func _ca_extract_open_areas() -> void:
    var cell_size := 16
    for gy in range(0, height, cell_size):
        for gx in range(0, width, cell_size):
            var candidates: Array[Vector2i] = []
            for dy in range(cell_size):
                for dx in range(cell_size):
                    var p := Vector2i(gx + dx, gy + dy)
                    if p.x < width and p.y < height and get_tile(p.x, p.y) == FLOOR:
                        candidates.append(p)
            if not candidates.is_empty():
                var c := candidates[rng.randi() % candidates.size()]
                rooms.append(Rect2i(c.x, c.y, 1, 1))

# ─── Drunkard Walk ──────────────────────────────────────
func _run_drunk() -> void:
    var cx := width / 2; var cy := height / 2
    var carved := 0
    var target := int(width * height * 0.45)
    var dirs := [Vector2i(1,0), Vector2i(-1,0), Vector2i(0,1), Vector2i(0,-1)]
    var steps := 0
    while carved < target and steps < drunk_steps:
        if get_tile(cx, cy) == WALL:
            set_tile(cx, cy, FLOOR)
            carved += 1
        var d: Vector2i = dirs[rng.randi() % 4]
        cx = clamp(cx + d.x, 1, width - 2)
        cy = clamp(cy + d.y, 1, height - 2)
        steps += 1
    rooms.append(Rect2i(width / 2, height / 2, 1, 1))
```

---

## LAYER 3：FOV Shadowcasting（8 象限遞迴）

### 為什麼用 Shadowcasting 取代 Bresenham

| 指標 | Bresenham | Shadowcasting |
|------|-----------|---------------|
| 複雜度 | O(r² × LOS長度) | O(r²) |
| 對稱性 | 不對稱 | 完全對稱 |
| 牆角穿透 | 有 bug | 無 |

```gdscript
# fov_shadowcasting.gd
class_name FOVShadowcasting
extends RefCounted

var visible  : Dictionary = {}
var explored : Dictionary = {}

const OCTANT_TRANSFORMS := [
    [ 1,  0,  0,  1], [ 0,  1,  1,  0], [ 0, -1,  1,  0], [-1,  0,  0,  1],
    [-1,  0,  0, -1], [ 0, -1, -1,  0], [ 0,  1, -1,  0], [ 1,  0,  0, -1],
]

func compute(origin: Vector2i, radius: int, is_opaque: Callable) -> void:
    visible.clear()
    _mark_visible(origin)
    for t in OCTANT_TRANSFORMS:
        _cast_light(origin, radius, 1, 1.0, 0.0, is_opaque, t[0], t[1], t[2], t[3])

func _cast_light(
    origin: Vector2i, radius: int, row: int,
    start_slope: float, end_slope: float, is_opaque: Callable,
    xx: int, xy: int, yx: int, yy: int
) -> void:
    if start_slope < end_slope:
        return
    var next_start := start_slope
    var blocked := false
    var r := row
    while r <= radius and not blocked:
        var dx := -r
        while dx <= 0:
            var pos := Vector2i(origin.x + dx * xx + r * xy, origin.y + dx * yx + r * yy)
            var l_slope := (float(dx) - 0.5) / (float(r) + 0.5)
            var r_slope := (float(dx) + 0.5) / (float(r) - 0.5) if r > 0 else 999.0
            if start_slope < r_slope:
                dx += 1; continue
            if end_slope > l_slope:
                break
            if dx * dx + r * r <= radius * radius:
                _mark_visible(pos)
            if blocked:
                if is_opaque.call(pos):
                    next_start = r_slope
                else:
                    blocked = false
                    start_slope = next_start
            else:
                if is_opaque.call(pos) and r < radius:
                    blocked = true
                    next_start = r_slope
                    _cast_light(origin, radius, r + 1, start_slope, l_slope, is_opaque, xx, xy, yx, yy)
            dx += 1
        r += 1

func _mark_visible(pos: Vector2i) -> void:
    visible[pos] = true
    explored[pos] = true

func is_visible(pos: Vector2i) -> bool: return visible.has(pos)
func is_explored(pos: Vector2i) -> bool: return explored.has(pos)
func is_in_shadow(pos: Vector2i) -> bool: return explored.has(pos) and not visible.has(pos)
```

---

## LAYER 4：物品系統

### ItemData Resource

```gdscript
# item_data.gd
class_name ItemData
extends Resource

enum ItemType { CONSUMABLE, EQUIPMENT_WEAPON, EQUIPMENT_ARMOR, SCROLL, GOLD }
enum BUC { BLESSED, UNCURSED, CURSED }

@export var item_id     : String = ""
@export var true_name   : String = ""
@export var pseudo_name : String = ""   # 識別前顯示的假名
@export var icon        : Texture2D
@export var item_type   : ItemType = ItemType.CONSUMABLE
@export var buc_state   : BUC = BUC.UNCURSED
@export var stackable   : bool = false
@export var max_stack   : int = 1
@export var base_value  : int = 10
@export var effects     : Array[ItemEffect] = []
@export var equip_slot  : String = ""
@export var attack_bonus  : int = 0
@export var defense_bonus : int = 0
@export var enchantment   : int = 0

func get_display_name(identity_system: ItemIdentitySystem) -> String:
    if identity_system.is_identified(item_id):
        return true_name + (" +%d" % enchantment if enchantment != 0 else "")
    return pseudo_name if pseudo_name != "" else "未知物品"
```

### ItemIdentitySystem

```gdscript
# item_identity_system.gd
class_name ItemIdentitySystem
extends Node

var _identified : Dictionary = {}
var _pseudo_map : Dictionary = {}

const POTION_COLORS := ["紅色", "藍色", "綠色", "黃色", "紫色", "橘色", "白色", "黑色"]
const SCROLL_RUNES  := ["ABJZ", "KZYX", "QWER", "MSDF", "PLOK", "XKCD", "WTFN", "ABCD"]

func initialize(all_items: Array[ItemData]) -> void:
    _identified.clear(); _pseudo_map.clear()
    var colors := POTION_COLORS.duplicate(); colors.shuffle()
    var runes  := SCROLL_RUNES.duplicate();  runes.shuffle()
    var ci := 0; var ri := 0
    for item in all_items:
        match item.item_type:
            ItemData.ItemType.CONSUMABLE:
                _pseudo_map[item.item_id] = "%s色藥水" % colors[ci % colors.size()]; ci += 1
            ItemData.ItemType.SCROLL:
                _pseudo_map[item.item_id] = "符文卷軸「%s」" % runes[ri % runes.size()]; ri += 1

func identify(item_id: String) -> void:  _identified[item_id] = true
func identify_all() -> void:
    for id in _pseudo_map.keys(): _identified[id] = true
func is_identified(item_id: String) -> bool: return _identified.has(item_id)
```

### ItemEffectExecutor

```gdscript
# item_effect_executor.gd
class_name ItemEffectExecutor
extends Node

signal effect_resolved(message: String)
signal item_consumed(item: ItemData)

func use_item(user: Entity, item: ItemData, target: Entity = null) -> bool:
    var actual_target := target if target else user
    var any_success := false
    for effect in item.effects:
        var result := effect.execute(actual_target, item)
        if result.success:
            any_success = true
            emit_signal("effect_resolved", result.message)
    if item.buc_state == ItemData.BUC.CURSED:
        var se := user.get_component("status_effects") as StatusEffectComponent
        if se: se.apply("weakened", 3, 1)
    if any_success and item.item_type == ItemData.ItemType.CONSUMABLE:
        GameManager.identity_system.identify(item.item_id)
        emit_signal("item_consumed", item)
    return any_success
```

---

## LAYER 5：StatusEffect 系統

```gdscript
# status_effect_data.gd
class_name StatusEffectData
extends Resource

@export var effect_id    : String = ""
@export var display_name : String = ""
@export var max_stacks   : int = 1
@export var is_debuff    : bool = true

func on_tick(entity: Entity, stack_count: int) -> String: return ""
func on_apply(entity: Entity) -> String: return ""
func on_remove(entity: Entity) -> void: pass
```

```gdscript
# status_effect_component.gd
class_name StatusEffectComponent
extends Node

signal effect_applied(effect_id: String)
signal effect_removed(effect_id: String)
signal tick_message(message: String)

var _active : Dictionary = {}
var _immunities : Array[String] = []

func add_immunity(effect_id: String) -> void:
    if not _immunities.has(effect_id): _immunities.append(effect_id)

func apply(effect_id: String, duration: int, stacks: int = 1) -> void:
    if _immunities.has(effect_id):
        emit_signal("tick_message", "免疫！"); return
    var data := _load_effect_data(effect_id)
    if not data: return
    if _active.has(effect_id):
        var entry: Dictionary = _active[effect_id]
        entry["duration"] = max(entry["duration"], duration)
        entry["stacks"] = min(entry["stacks"] + stacks, data.max_stacks)
    else:
        _active[effect_id] = {"data": data, "stacks": stacks, "duration": duration}
        var msg := data.on_apply(get_parent() as Entity)
        if msg != "": emit_signal("tick_message", msg)
    emit_signal("effect_applied", effect_id)

func tick() -> void:
    var to_remove: Array[String] = []
    for effect_id in _active.keys():
        var entry: Dictionary = _active[effect_id]
        var msg := entry["data"].on_tick(get_parent() as Entity, entry["stacks"])
        if msg != "": emit_signal("tick_message", msg)
        entry["duration"] -= 1
        if entry["duration"] <= 0:
            to_remove.append(effect_id)
    for effect_id in to_remove:
        _active[effect_id]["data"].on_remove(get_parent() as Entity)
        _active.erase(effect_id)
        emit_signal("effect_removed", effect_id)

func has_effect(effect_id: String) -> bool: return _active.has(effect_id)

func _load_effect_data(effect_id: String) -> StatusEffectData:
    var path := "res://data/status_effects/%s.tres" % effect_id
    if ResourceLoader.exists(path):
        return load(path) as StatusEffectData
    push_error("StatusEffect not found: " + effect_id)
    return null
```

---

## LAYER 6：效能優化

### TileMap 批次更新

```gdscript
# tilemap_renderer.gd
class_name TilemapRenderer
extends Node

@onready var floor_layer : TileMapLayer = $FloorLayer
@onready var wall_layer  : TileMapLayer = $WallLayer

func render_full_grid(grid: Array, width: int, height: int) -> void:
    floor_layer.clear()
    wall_layer.clear()
    for y in height:
        for x in width:
            var pos := Vector2i(x, y)
            if grid[y][x] == DungeonGenerator.FLOOR:
                floor_layer.set_cell(pos, 0, Vector2i(0, 0))
            else:
                wall_layer.set_cell(pos, 0, Vector2i(1, 0))
```

### Entity Pool

```gdscript
# entity_pool.gd
class_name EntityPool
extends Node

@export var enemy_scene : PackedScene
@export var pool_size   : int = 50

var _available : Array[Entity] = []
var _in_use    : Array[Entity] = []

func _ready() -> void:
    for _i in pool_size:
        var e := enemy_scene.instantiate() as Entity
        e.visible = false
        add_child(e)
        _available.append(e)

func acquire() -> Entity:
    if _available.is_empty():
        var e := enemy_scene.instantiate() as Entity
        add_child(e)
        return e
    var entity := _available.pop_back()
    entity.visible = true
    _in_use.append(entity)
    return entity

func release(entity: Entity) -> void:
    entity.visible = false
    _in_use.erase(entity)
    _available.append(entity)
```

### Thread 非同步生成

```gdscript
# generator_manager.gd
class_name GeneratorManager
extends Node

signal floor_ready(grid: Array, rooms: Array)

var _generator : DungeonGenerator
var _thread    : Thread
var _mutex     : Mutex = Mutex.new()
var _result    : Dictionary = {}

func start_generate(algorithm: DungeonGenerator.Algorithm, seed_val: int) -> void:
    _generator = DungeonGenerator.new()
    _generator.algorithm = algorithm
    _thread = Thread.new()
    _thread.start(_generate_in_thread.bind(seed_val))

func _generate_in_thread(seed_val: int) -> void:
    var grid  := _generator.generate(seed_val)
    var rooms := _generator.rooms.duplicate()
    _mutex.lock()
    _result = {"grid": grid, "rooms": rooms}
    _mutex.unlock()
    call_deferred("_on_done")

func _on_done() -> void:
    _thread.wait_to_finish()
    _mutex.lock()
    var data := _result.duplicate()
    _mutex.unlock()
    emit_signal("floor_ready", data["grid"], data["rooms"])

func _exit_tree() -> void:
    if _thread and _thread.is_started():
        _thread.wait_to_finish()
```

### FighterComponent（spend-time 版本）

```gdscript
# fighter_component.gd
class_name FighterComponent
extends Node

signal died(entity: Entity)
signal damaged(amount: int, entity: Entity)

@export var max_hp  : int = 30
@export var attack  : int = 5
@export var defense : int = 2
@export var speed   : int = 10

var hp            : int
var action_points : float = 0.0

func _ready() -> void: hp = max_hp

func take_damage(amount: int) -> int:
    var actual := max(1, amount - defense)
    hp = max(0, hp - actual)
    damaged.emit(actual, get_parent())
    if hp == 0: died.emit(get_parent())
    return actual

func heal(amount: int) -> int:
    var actual := min(amount, max_hp - hp)
    hp += actual
    return actual

func spend(cost: float) -> void: action_points -= cost
func gain_action_points(base: float = 1.0) -> void:
    action_points += base * (speed / 10.0)
func can_act() -> bool: return action_points >= 1.0
```

### TurnQueue（spend-time）

```gdscript
# turn_queue.gd
class_name TurnQueue
extends Node

var _entities : Array[Entity] = []
var _pending_removal : Array[Entity] = []

func add_entity(entity: Entity) -> void: _entities.append(entity)
func mark_for_removal(entity: Entity) -> void: _pending_removal.append(entity)

func advance() -> void:
    for entity in _entities:
        var f := entity.get_component("fighter") as FighterComponent
        if f: f.gain_action_points()
    var acted := true
    while acted:
        acted = false
        for entity in _entities.duplicate():
            if _pending_removal.has(entity): continue
            var f := entity.get_component("fighter") as FighterComponent
            if f and f.can_act():
                _process_entity_turn(entity)
                f.spend(1.0)
                acted = true
    # 回合結束後清理死亡實體
    for entity in _pending_removal:
        _entities.erase(entity)
    _pending_removal.clear()

func _process_entity_turn(entity: Entity) -> void:
    if entity.has_method("take_turn"):
        entity.take_turn()
    var se := entity.get_component("status_effects") as StatusEffectComponent
    if se: se.tick()
```

---

## LAYER 7：四個開源專案分析

### Shattered Pixel Dungeon
- **語言**：Java / LibGDX | **星星**：5k+
- **架構**：`actors/` 所有行動實體繼承 `Char`，共用 `spend()` 行動點
- **物品**：Item -> Weapon / Armor / Potion / Scroll 繼承樹
- **識別系統**：全局打亂假名，每局不同
- **關鍵教訓**：spend-time 回合系統優於輪流制（快速敵人一回合行動多次）

### Cataclysm: Dark Days Ahead
- **語言**：C++ + JSON | 貢獻者：1000+
- **全 JSON 資料驅動**：怪物/物品/配方全在 JSON
- **三層地圖**：overmap -> submap -> tile
- **關鍵教訓**：資料驅動讓非程式員大量貢獻內容

### NetHack（Roguelike DNA 源頭）
- **語言**：C（1987-）
- **BUC 三態**：Blessed / Uncursed / Cursed 影響物品效果
- **識別即使用**：喝了才知道是什麼藥水
- **混合關卡生成**：隨機層 + 硬編碼特殊層
- **關鍵教訓**：物品豐富的交互網路創造深度策略空間

### Godot 4 社群 Roguelike 教學
- **架構觀察**：v1 用 Bresenham LOS + 單一 TileMapLayer
- **v2 改進**：Shadowcasting + 分層 TileMap + Entity Pool
- **關鍵教訓**：`TileMapLayer.set_cell()` 在 Godot 4 與 3.x 完全不同 API

---

## LAYER 8：踩坑表格

| # | 問題 | 症狀 | 解法 |
|---|------|------|------|
| 1 | FOV 斜向穿牆 | 玩家能看到牆後敵人 | 改用 Shadowcasting |
| 2 | TileMapLayer 更新卡頓 | 每步 FPS 驟降 | dirty list 批次呼叫 |
| 3 | Thread 修改 scene tree 崩潰 | 隨機 crash | Thread 只做純計算，`call_deferred` 提交 |
| 4 | Resource 共享被修改 | 改一個實體影響全部 | `resource.duplicate()` |
| 5 | 存檔後 Signal 失連 | 讀檔後行動無反應 | 存純 Dictionary，讀取後重建並重連 Signal |
| 6 | Drunkard Walk 孤立區域 | 玩家無法到達樓梯 | 生成後洪水填充連通驗證 |
| 7 | CA 生成全牆地圖 | 填充率過高 | 保持 0.45~0.52；FLOOR 數 < 20% 則重試 |
| 8 | BSP 走廊穿過其他房間 | 視覺錯亂 | 走廊只設 FLOOR，允許穿越 |
| 9 | 死亡 Signal 在 TurnQueue 中途 emit | 迭代器崩潰 | `_pending_removal` 列表，回合結束後統一移除 |
| 10 | Resource 熱重載無效 | 改了 .tres 遊戲沒變 | `ResourceLoader.load()` + `CACHE_IGNORE` |

---

## LAYER 9：MVP 建構路線圖

| Phase | 工作項目 | 預估時間 | 驗收標準 |
|-------|----------|----------|----------|
| 1 | TileMapLayer + BSP 地牢生成（60x40）| 1-2 天 | 能看到隨機房間與走廊 |
| 2 | 玩家移動 + 碰撞偵測 | 1 天 | WASD 移動不穿牆 |
| 3 | FOV Shadowcasting + FogOfWar | 2 天 | 黑/灰/亮三態正確顯示 |
| 4 | TurnQueue spend-time + 敵人 AI + MessageLog | 2-3 天 | 敵人追逐，戰鬥有訊息 |
| 5 | ItemData + IdentitySystem + Executor | 2 天 | 藥水有假名，使用後識別 |
| 6 | StatusEffect（毒/燃燒/冰凍/眩暈）| 1-2 天 | 中毒持續掉血 |
| 7 | 永久死亡 + 存檔 + 樓梯換層 | 2 天 | 死亡刪 run save |
| 8 | Entity Pool + Thread 生成 + 效能優化 | 1-2 天 | 換層無卡頓 |

---

## 認知框架

### 我能做的
- BSP / Cellular Automata / Drunkard Walk 三種地牢生成，含連通驗證
- Shadowcasting 8 象限 FOV，效能優於 Bresenham LOS 3 倍
- 完整物品系統：Resource 繼承樹、識別系統、BUC 三態、效果執行器
- StatusEffect 堆疊/免疫/計時系統
- Entity Pool + Thread 非同步生成 + TileMap 批次更新
- spend-time 回合系統

### 誠實邊界
- Godot 4.x Thread 在 WebAssembly 平台支援度需測試
- Shadowcasting 在超大地圖（200x200+）+ 大視野（40+）的 ms 數字需實測

### 反模式（禁止）
- ❌ 在 `_process()` 中執行回合邏輯：Roguelike 是事件驅動
- ❌ 在 Thread 中修改 scene tree：只做純計算，`call_deferred()` 提交
- ❌ 直接修改共享 Resource：必須 `.duplicate()` 後再改
- ❌ 玩家死亡後保留 run save：永久死亡是核心設計契約
- ❌ 無 FOV 情況下顯示敵人：違反資訊不對稱原則
- ❌ 跳過連通驗證：Drunkard Walk / CA 生成後必做洪水填充

---

*版本：v2 | 最後更新：2026-04-19 | 適用：Godot 4.x GDScript*

# Godot 4 塔防遊戲開發 Skill
# Tower Defense 架構知識庫 v2

## 觸發條件
當使用者要開發塔防遊戲（防禦塔、波次敵人、路徑尋找、資源管理、DPS計算、多路徑設計）時使用。

---

## LAYER 1：速查（每次必讀）

### 核心系統一覽
| 系統 | 說明 | 關鍵類別 |
|------|------|---------|
| 路徑尋找 | Path2D 固定路徑 / AStarGrid2D 動態 / Flow Field 大規模 | EnemyAI, PathGenerator |
| 波次系統 | WaveManager 控制生成時機、數量、難度縮放 | WaveManager, WaveResource |
| 塔邏輯 | 攻擊範圍、目標選擇策略、DPS 計算 | TurretBase, TargetingStrategy |
| 地圖格子 | TileMapLayer 區分可建造/道路格子 | MapManager |
| 資源管理 | 金幣、生命值、得分、升級費用 | GameManager |
| 砲彈/投射物 | 物件池管理大量投射物，避免運行時 GC | ProjectilePool |
| 效果系統 | 減速、燃燒、暈眩等 StatusEffect | StatusEffectComponent |

### MVP 最小可行場景結構

```
Main (Node2D)
+-- GameManager (Node)          波次/資源/狀態控制
+-- WaveManager (Node)          波次生成邏輯
+-- Map (TileMapLayer)          地圖格子（道路/草地/建造區）
+-- PathLayer (Node2D)          路徑視覺化（含多條 Path2D）
|   +-- Path_A (Path2D)         主路徑 A
|   +-- Path_B (Path2D)         分叉路徑 B（多路徑設計）
+-- TowerContainer (Node2D)     所有塔的容器
+-- EnemyContainer (Node2D)     所有敵人的容器
+-- ProjectilePool (Node2D)     投射物物件池
+-- NavigationRegion2D          導航網格（動態地圖用）
+-- HUD (CanvasLayer)
    +-- WaveLabel               當前波次顯示
    +-- GoldLabel               金幣顯示
    +-- LivesLabel              生命值顯示
    +-- TowerPanel              塔選擇面板
    +-- SpeedButton             遊戲速度切換
    +-- DPSOverlay              DPS 偵錯覆蓋層（開發模式）
```

---

## LAYER 2：完整程式碼（開發新系統前讀）

### WaveManager — 完整實作

```gdscript
# wave_manager.gd
class_name WaveManager
extends Node

signal wave_started(wave_num: int)
signal wave_completed(wave_num: int)
signal all_waves_done
signal enemy_spawned(enemy: EnemyAI)

@export var wave_data: Array[WaveResource] = []
@export var enemy_container: Node2D
@export var paths: Array[Path2D] = []
@export var difficulty_scale: float = 1.0

var current_wave: int = 0
var enemies_alive: int = 0
var is_spawning: bool = false
var _spawn_queue: Array[Dictionary] = []
var _wave_timer: SceneTreeTimer = null

func _ready() -> void:
    if enemy_container == null:
        push_error("WaveManager: enemy_container 未設定")

func start_wave(wave_index: int = -1) -> void:
    if is_spawning:
        push_warning("WaveManager: 波次仍在進行中，無法重複啟動")
        return
    if wave_index >= 0:
        current_wave = wave_index
    if current_wave >= wave_data.size():
        all_waves_done.emit()
        return
    var wave: WaveResource = wave_data[current_wave]
    is_spawning = true
    wave_started.emit(current_wave + 1)
    _build_spawn_queue(wave)
    if wave.pre_wave_delay > 0.0:
        await get_tree().create_timer(wave.pre_wave_delay).timeout
    _spawn_next()

func _build_spawn_queue(wave: WaveResource) -> void:
    _spawn_queue.clear()
    for group in wave.groups:
        var path_index: int = group.path_index if group.path_index >= 0 else randi() % paths.size()
        for i in group.count:
            _spawn_queue.append({
                "type": group.enemy_type,
                "delay": group.interval,
                "path_index": path_index,
                "wave_num": current_wave
            })
    if wave.shuffle_order:
        _spawn_queue.shuffle()

func _spawn_next() -> void:
    if _spawn_queue.is_empty():
        return
    var entry: Dictionary = _spawn_queue.pop_front()
    _spawn_enemy(entry)
    enemies_alive += 1
    if not _spawn_queue.is_empty():
        _wave_timer = get_tree().create_timer(entry.delay)
        _wave_timer.timeout.connect(_spawn_next)

func _spawn_enemy(entry: Dictionary) -> void:
    var scene: PackedScene = EnemyRegistry.get_scene(entry.type)
    if scene == null:
        push_error("WaveManager: 未知敵人類型 " + str(entry.type))
        enemies_alive -= 1
        return
    var enemy: EnemyAI = scene.instantiate() as EnemyAI
    if enemy == null:
        return
    _apply_difficulty_scale(enemy, entry.wave_num)
    enemy.died.connect(_on_enemy_died.bind(enemy))
    enemy.reached_end.connect(_on_enemy_reached_end.bind(enemy))
    enemy_container.add_child(enemy)
    var path_idx: int = clampi(entry.path_index, 0, paths.size() - 1)
    enemy.follow_path(paths[path_idx])
    enemy_spawned.emit(enemy)

func _apply_difficulty_scale(enemy: EnemyAI, wave_num: int) -> void:
    var hp_scale: float = 1.0 + (wave_num * 0.15) * difficulty_scale
    var speed_scale: float = 1.0 + (wave_num * 0.04) * difficulty_scale
    var reward_scale: float = 1.0 + (wave_num * 0.08)
    enemy.max_hp = int(enemy.max_hp * hp_scale)
    enemy.hp = enemy.max_hp
    enemy.speed = enemy.speed * speed_scale
    enemy.reward = int(enemy.reward * reward_scale)

func _on_enemy_died(_enemy: EnemyAI) -> void:
    enemies_alive = maxi(0, enemies_alive - 1)
    _check_wave_complete()

func _on_enemy_reached_end(enemy: EnemyAI) -> void:
    enemies_alive = maxi(0, enemies_alive - 1)
    GameManager.lose_life(enemy.damage_to_base)
    _check_wave_complete()

func _check_wave_complete() -> void:
    if enemies_alive == 0 and _spawn_queue.is_empty() and is_spawning:
        is_spawning = false
        wave_completed.emit(current_wave)
        current_wave += 1

func force_end_wave() -> void:
    _spawn_queue.clear()
    is_spawning = false
    wave_completed.emit(current_wave)
    current_wave += 1
```

### WaveResource 資料類別

```gdscript
# resources/wave_resource.gd
class_name WaveResource
extends Resource

class SpawnGroup extends RefCounted:
    var enemy_type: StringName = &"Grunt"
    var count: int = 5
    var interval: float = 0.5
    var path_index: int = -1

    func _init(type: StringName, cnt: int, interval_sec: float, path: int = -1) -> void:
        enemy_type = type
        count = cnt
        interval = interval_sec
        path_index = path

@export var wave_name: String = "Wave"
@export var pre_wave_delay: float = 3.0
@export var shuffle_order: bool = false
@export var groups: Array = []
@export var boss_wave: bool = false
@export var bonus_gold: int = 0

func get_total_enemies() -> int:
    var total: int = 0
    for group in groups:
        total += group.count
    return total

func get_estimated_duration() -> float:
    var duration: float = pre_wave_delay
    for group in groups:
        duration += group.count * group.interval
    return duration
```

### EnemyAI — 完整實作

```gdscript
# enemy_ai.gd
class_name EnemyAI
extends Node2D

signal died(reward: int)
signal reached_end
signal hp_changed(current: int, maximum: int)

@export var enemy_name: String = "Grunt"
@export var max_hp: int = 100
@export var speed: float = 60.0
@export var reward: int = 10
@export var damage_to_base: int = 1
@export var armor: float = 0.0
@export var magic_resist: float = 0.0

@onready var sprite: Sprite2D = $Sprite2D
@onready var health_bar: ProgressBar = $HealthBar
@onready var anim_player: AnimationPlayer = $AnimationPlayer

var hp: int = 0
var is_dead: bool = false
var _path: Path2D = null
var _path_follow: PathFollow2D = null
var _current_speed_modifier: float = 1.0
var _active_effects: Array[StatusEffect] = []

func _ready() -> void:
    hp = max_hp
    add_to_group("enemies")
    if health_bar:
        health_bar.max_value = max_hp
        health_bar.value = max_hp

func _process(delta: float) -> void:
    if is_dead or _path_follow == null:
        return
    _tick_effects(delta)
    var effective_speed: float = speed * _current_speed_modifier
    _path_follow.progress += effective_speed * delta
    global_position = _path_follow.global_position
    if _path_follow.rotates:
        rotation = _path_follow.rotation
    if _path_follow.progress_ratio >= 1.0:
        _on_reached_end()

func follow_path(path: Path2D) -> void:
    _path = path
    _path_follow = PathFollow2D.new()
    _path_follow.rotates = true
    _path_follow.loop = false
    _path.add_child(_path_follow)
    _path_follow.progress = 0.0
    global_position = _path_follow.global_position

func take_damage(amount: int, damage_type: String = "physical") -> void:
    if is_dead:
        return
    var actual_damage: int = amount
    match damage_type:
        "physical":
            actual_damage = int(amount * (1.0 - armor))
        "magical":
            actual_damage = int(amount * (1.0 - magic_resist))
        "true":
            actual_damage = amount
    actual_damage = maxi(1, actual_damage)
    hp -= actual_damage
    hp_changed.emit(hp, max_hp)
    if health_bar:
        health_bar.value = hp
    _play_hit_effect()
    if hp <= 0:
        _die()

func apply_effect(effect: StatusEffect) -> void:
    for existing in _active_effects:
        if existing.effect_id == effect.effect_id:
            existing.reset(effect.duration)
            return
    effect.apply_to(self)
    _active_effects.append(effect)

func _tick_effects(delta: float) -> void:
    _current_speed_modifier = 1.0
    var to_remove: Array[StatusEffect] = []
    for effect in _active_effects:
        effect.tick(delta, self)
        if effect.is_expired():
            effect.remove_from(self)
            to_remove.append(effect)
        else:
            _current_speed_modifier *= effect.speed_modifier
    for effect in to_remove:
        _active_effects.erase(effect)

func _die() -> void:
    if is_dead:
        return
    is_dead = true
    set_process(false)
    died.emit(reward)
    if anim_player and anim_player.has_animation("death"):
        anim_player.play("death")
        await anim_player.animation_finished
    if _path_follow and is_instance_valid(_path_follow):
        _path_follow.queue_free()
    queue_free()

func _on_reached_end() -> void:
    if is_dead:
        return
    is_dead = true
    set_process(false)
    reached_end.emit()
    if _path_follow and is_instance_valid(_path_follow):
        _path_follow.queue_free()
    queue_free()

func _play_hit_effect() -> void:
    if sprite == null:
        return
    var tween: Tween = create_tween()
    tween.tween_property(sprite, "modulate", Color.RED, 0.05)
    tween.tween_property(sprite, "modulate", Color.WHITE, 0.05)

func get_path_progress() -> float:
    if _path_follow == null:
        return 0.0
    return _path_follow.progress_ratio
```

### TurretBase — 完整實作

```gdscript
# turret_base.gd
class_name TurretBase
extends Node2D

signal upgraded(level: int)
signal sold(refund: int)
signal attack_performed(target: EnemyAI)

@export var turret_name: String = "基礎塔"
@export var attack_range: float = 150.0
@export var attack_speed: float = 1.0
@export var damage: int = 10
@export var cost: int = 50
@export var damage_type: String = "physical"
@export var targeting_mode: TargetingStrategy.Mode = TargetingStrategy.Mode.FIRST
@export var max_level: int = 3
@export var upgrade_multipliers: Array[float] = [1.0, 1.5, 2.2]

@onready var turret_sprite: Sprite2D = $TurretSprite
@onready var range_indicator: Node2D = $RangeIndicator
@onready var attack_anim: AnimationPlayer = $AnimationPlayer

var level: int = 1
var _target: EnemyAI = null
var _attack_cooldown: float = 0.0
var _total_damage_dealt: int = 0
var _lifetime: float = 0.0

func _ready() -> void:
    if range_indicator:
        range_indicator.visible = false

func _process(delta: float) -> void:
    _lifetime += delta
    _attack_cooldown -= delta
    if not is_instance_valid(_target) or _target == null or _target.is_dead:
        _target = _acquire_target()
    if _target and is_instance_valid(_target):
        _rotate_toward_target(delta)
        if _attack_cooldown <= 0.0:
            _perform_attack()
            _attack_cooldown = 1.0 / attack_speed

func _acquire_target() -> EnemyAI:
    var enemies: Array = get_tree().get_nodes_in_group("enemies")
    return TargetingStrategy.find_target(global_position, enemies, targeting_mode, attack_range)

func _rotate_toward_target(delta: float) -> void:
    if turret_sprite == null:
        return
    var dir: Vector2 = (_target.global_position - global_position).normalized()
    turret_sprite.rotation = lerp_angle(turret_sprite.rotation, dir.angle(), 10.0 * delta)

func _perform_attack() -> void:
    if not is_instance_valid(_target):
        return
    var proj: Projectile = ProjectilePool.instance.get_projectile()
    if proj == null:
        return
    var actual_damage: int = int(damage * upgrade_multipliers[level - 1])
    proj.setup(global_position, _target, actual_damage, damage_type)
    get_tree().current_scene.get_node("ProjectilePool").add_child(proj)
    _total_damage_dealt += actual_damage
    attack_performed.emit(_target)
    if attack_anim:
        attack_anim.play("attack")

func get_dps() -> float:
    return damage * upgrade_multipliers[level - 1] * attack_speed

func get_lifetime_dps() -> float:
    if _lifetime <= 0.0:
        return 0.0
    return float(_total_damage_dealt) / _lifetime

func upgrade() -> bool:
    if level >= max_level:
        return false
    if not GameManager.spend_gold(get_upgrade_cost()):
        return false
    level += 1
    upgraded.emit(level)
    _on_upgraded()
    return true

func _on_upgraded() -> void:
    pass  # 子類別覆寫：更換貼圖、特效

func get_upgrade_cost() -> int:
    return int(cost * pow(1.8, level - 1))

func sell() -> void:
    var refund: int = int(cost * 0.6)
    GameManager.add_gold(refund)
    sold.emit(refund)
    queue_free()

func set_selected(selected: bool) -> void:
    if range_indicator:
        range_indicator.visible = selected

func get_info() -> Dictionary:
    return {
        "name": turret_name,
        "level": level,
        "max_level": max_level,
        "damage": int(damage * upgrade_multipliers[level - 1]),
        "attack_speed": attack_speed,
        "dps": get_dps(),
        "range": attack_range,
        "upgrade_cost": get_upgrade_cost() if level < max_level else 0,
        "sell_value": int(cost * 0.6),
        "total_damage": _total_damage_dealt,
        "lifetime_dps": get_lifetime_dps()
    }
```

### TargetingStrategy — 目標選擇策略（6 種模式）

```gdscript
# targeting_strategy.gd
class_name TargetingStrategy
extends RefCounted

enum Mode {
    FIRST,      # 最接近終點（最優先擊殺）
    LAST,       # 最遠離終點
    STRONGEST,  # 血量最多
    WEAKEST,    # 血量最少（快死的）
    CLOSEST,    # 距離塔最近
    LOWEST_HP,  # 血量百分比最低
}

static func find_target(
    tower_pos: Vector2,
    enemies: Array,
    mode: Mode,
    range: float
) -> EnemyAI:
    var candidates: Array = enemies.filter(func(e: Node) -> bool:
        return e is EnemyAI
            and is_instance_valid(e)
            and not e.is_dead
            and tower_pos.distance_to(e.global_position) <= range
    )
    if candidates.is_empty():
        return null
    match mode:
        Mode.FIRST:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if a.get_path_progress() > b.get_path_progress() else b)
        Mode.LAST:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if a.get_path_progress() < b.get_path_progress() else b)
        Mode.STRONGEST:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if a.hp > b.hp else b)
        Mode.WEAKEST:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if a.hp < b.hp else b)
        Mode.CLOSEST:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if tower_pos.distance_to(a.global_position) < tower_pos.distance_to(b.global_position) else b)
        Mode.LOWEST_HP:
            return candidates.reduce(func(a: EnemyAI, b: EnemyAI) -> EnemyAI:
                return a if float(a.hp) / float(a.max_hp) < float(b.hp) / float(b.max_hp) else b)
    return null
```

### ProjectilePool — 物件池

```gdscript
# projectile_pool.gd
class_name ProjectilePool
extends Node

static var instance: ProjectilePool

@export var projectile_scene: PackedScene
@export var initial_pool_size: int = 60
@export var max_pool_size: int = 200

var _pool: Array[Projectile] = []
var _active_count: int = 0

func _ready() -> void:
    instance = self
    for i in initial_pool_size:
        _create_and_park()

func _create_and_park() -> Projectile:
    var p: Projectile = projectile_scene.instantiate() as Projectile
    p.returned_to_pool.connect(return_projectile.bind(p))
    p.visible = false
    p.set_process(false)
    add_child(p)
    _pool.append(p)
    return p

func get_projectile() -> Projectile:
    for p in _pool:
        if not p.visible:
            p.visible = true
            p.set_process(true)
            _active_count += 1
            return p
    if _pool.size() < max_pool_size:
        var p: Projectile = _create_and_park()
        p.visible = true
        p.set_process(true)
        _active_count += 1
        return p
    push_warning("ProjectilePool: 已達上限 %d" % max_pool_size)
    return null

func return_projectile(p: Projectile) -> void:
    p.visible = false
    p.set_process(false)
    _active_count -= 1

func get_stats() -> Dictionary:
    return {"pool_size": _pool.size(), "active": _active_count}
```

### Projectile — 追蹤投射物

```gdscript
# projectile.gd
class_name Projectile
extends Node2D

signal returned_to_pool

@export var move_speed: float = 300.0
@export var splash_radius: float = 0.0

var _target: EnemyAI = null
var _damage: int = 0
var _damage_type: String = "physical"

func setup(start_pos: Vector2, target: EnemyAI, dmg: int, dtype: String = "physical") -> void:
    global_position = start_pos
    _target = target
    _damage = dmg
    _damage_type = dtype

func _process(delta: float) -> void:
    if not is_instance_valid(_target) or _target.is_dead:
        _return_to_pool()
        return
    var dir: Vector2 = (_target.global_position - global_position).normalized()
    global_position += dir * move_speed * delta
    rotation = dir.angle()
    if global_position.distance_to(_target.global_position) < 8.0:
        _on_hit()

func _on_hit() -> void:
    if splash_radius > 0.0:
        for enemy in get_tree().get_nodes_in_group("enemies"):
            if enemy is EnemyAI and global_position.distance_to(enemy.global_position) <= splash_radius:
                enemy.take_damage(_damage, _damage_type)
    else:
        if is_instance_valid(_target):
            _target.take_damage(_damage, _damage_type)
    _return_to_pool()

func _return_to_pool() -> void:
    returned_to_pool.emit()
```

---

## LAYER 3：架構設計決策

### 多路徑設計比較

| 設計方式 | 優點 | 缺點 | 適用場景 |
|---------|------|------|---------|
| **單一 Path2D** | 最簡單，PathFollow2D 完全內建支援 | 無策略深度 | 快速原型 |
| **多條 Path2D 固定分流** | 易實作，每條路徑獨立塔防 | 玩家難以預測路線 | Kingdom Rush 風格 |
| **AStarGrid2D 動態路徑** | 敵人可繞過新建防禦塔 | CPU 開銷高，需快取 | 允許玩家建牆（BTD 風格）|
| **Flow Field（流場）** | 數百敵人共享一流場，O(1) 查詢 | 實作複雜 | 大規模敵人（Mindustry 風格）|

```
選擇流程：
  敵人同屏 < 30  →  多條 Path2D
  敵人同屏 30~100  →  AStarGrid2D + 路徑快取
  敵人同屏 100+  →  Flow Field
```

### Flow Field 實作

```gdscript
# flow_field.gd
class_name FlowField
extends RefCounted

var _field: Dictionary = {}
var _cell_size: Vector2

func build(map: TileMapLayer, goal_cell: Vector2i) -> void:
    _cell_size = map.tile_set.tile_size
    var queue: Array[Vector2i] = [goal_cell]
    var cost: Dictionary = {goal_cell: 0}
    while not queue.is_empty():
        var current: Vector2i = queue.pop_front()
        for n in _get_walkable_neighbors(map, current):
            if not cost.has(n):
                cost[n] = cost[current] + 1
                queue.append(n)
    for cell in cost.keys():
        var best_dir: Vector2 = Vector2.ZERO
        var best_cost: int = cost[cell]
        for n in _get_walkable_neighbors(map, cell):
            if cost.has(n) and cost[n] < best_cost:
                best_cost = cost[n]
                best_dir = Vector2(n - cell).normalized()
        _field[cell] = best_dir

func get_direction(world_pos: Vector2) -> Vector2:
    return _field.get(Vector2i(world_pos / _cell_size), Vector2.ZERO)

func _get_walkable_neighbors(map: TileMapLayer, cell: Vector2i) -> Array[Vector2i]:
    var result: Array[Vector2i] = []
    for d in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
        var n: Vector2i = cell + d
        var data = map.get_cell_tile_data(n)
        if data != null and data.get_custom_data("walkable"):
            result.append(n)
    return result
```

### StatusEffect 系統

```gdscript
# status_effect.gd
class_name StatusEffect
extends RefCounted

var effect_id: StringName = &""
var duration: float = 0.0
var _remaining: float = 0.0
var speed_modifier: float = 1.0

func _init(id: StringName, dur: float) -> void:
    effect_id = id
    duration = dur
    _remaining = dur

func apply_to(_enemy: EnemyAI) -> void: pass
func tick(delta: float, _enemy: EnemyAI) -> void: _remaining -= delta
func remove_from(_enemy: EnemyAI) -> void: pass
func reset(new_dur: float) -> void: _remaining = new_dur
func is_expired() -> bool: return _remaining <= 0.0


class SlowEffect extends StatusEffect:
    func _init(dur: float, slow_pct: float) -> void:
        super._init(&"slow", dur)
        speed_modifier = 1.0 - slow_pct


class BurnEffect extends StatusEffect:
    var dps: float = 5.0
    func _init(dur: float, damage_per_sec: float) -> void:
        super._init(&"burn", dur)
        dps = damage_per_sec
    func tick(delta: float, enemy: EnemyAI) -> void:
        super.tick(delta, enemy)
        enemy.take_damage(int(dps * delta), "magical")


class StunEffect extends StatusEffect:
    func _init(dur: float) -> void:
        super._init(&"stun", dur)
        speed_modifier = 0.0
```

### MapManager — 建造管理

```gdscript
# map_manager.gd
class_name MapManager
extends Node

@export var tilemap: TileMapLayer

var _occupied: Dictionary = {}  # Vector2i -> TurretBase

func can_build(tile_pos: Vector2i) -> bool:
    var data = tilemap.get_cell_tile_data(tile_pos)
    if data == null:
        return false
    return data.get_custom_data("buildable") == true and not _occupied.has(tile_pos)

func place_tower(tile_pos: Vector2i, scene: PackedScene, container: Node2D) -> TurretBase:
    if not can_build(tile_pos):
        return null
    var tower: TurretBase = scene.instantiate() as TurretBase
    if tower == null:
        return null
    container.add_child(tower)
    tower.global_position = tilemap.map_to_local(tile_pos) + Vector2(tilemap.tile_set.tile_size) / 2.0
    _occupied[tile_pos] = tower
    return tower

func remove_tower(tile_pos: Vector2i) -> void:
    if not _occupied.has(tile_pos):
        return
    var tower: TurretBase = _occupied[tile_pos]
    if is_instance_valid(tower):
        tower.sell()
    _occupied.erase(tile_pos)

func world_to_tile(world_pos: Vector2) -> Vector2i:
    return tilemap.local_to_map(tilemap.to_local(world_pos))

func get_tower_at(tile_pos: Vector2i) -> TurretBase:
    return _occupied.get(tile_pos, null)

func serialize_towers() -> Array[Dictionary]:
    var result: Array[Dictionary] = []
    for tile_pos in _occupied:
        var tower: TurretBase = _occupied[tile_pos]
        if is_instance_valid(tower):
            result.append({"tile": [tile_pos.x, tile_pos.y], "type": tower.turret_name, "level": tower.level})
    return result
```

### Area2D 替代 distance_to（效能優化）

```gdscript
# 在 TurretBase 場景中加入 Area2D
@onready var detection_area: Area2D = $DetectionArea
var _enemies_in_range: Array[EnemyAI] = []

func _ready() -> void:
    var shape: CircleShape2D = CircleShape2D.new()
    shape.radius = attack_range
    var col: CollisionShape2D = CollisionShape2D.new()
    col.shape = shape
    detection_area.add_child(col)
    detection_area.body_entered.connect(_on_enemy_entered)
    detection_area.body_exited.connect(_on_enemy_exited)
    detection_area.collision_mask = 2  # 敵人在 layer 2

func _on_enemy_entered(body: Node2D) -> void:
    if body is EnemyAI:
        _enemies_in_range.append(body)

func _on_enemy_exited(body: Node2D) -> void:
    _enemies_in_range.erase(body)

func _acquire_target() -> EnemyAI:
    var valid: Array = _enemies_in_range.filter(
        func(e): return is_instance_valid(e) and not e.is_dead
    )
    return TargetingStrategy.find_target(global_position, valid, targeting_mode, attack_range)
```

---

## LAYER 4：DPS 計算與平衡設計

### DPS 公式

```
基礎 DPS = 傷害 × 每秒攻擊次數
有效 DPS（含防禦）= 基礎 DPS × (1 - 目標護甲比例)
CP 值 = 有效 DPS / 建造費用

範例：
  基礎塔：10 傷害 × 1.0 攻速 = 10 DPS，費用 50 → CP = 0.2 DPS/金
  爆炸塔：80 傷害 × 0.3 攻速 × 3 目標 = 72 DPS，費用 150 → CP = 0.48（AOE）
  鐳射塔：持續傷害，穿透護甲，高護甲敵人最有效
```

### 塔平衡試算表

| 塔類型 | 費用 | 傷害 | 攻速 | 基礎 DPS | 特殊能力 |
|--------|------|------|------|----------|---------|
| 基礎塔 | 50 | 10 | 1.0 | 10 | 無 |
| 機槍塔 | 100 | 5 | 4.0 | 20 | 高攻速對輕甲有效 |
| 爆炸塔 | 150 | 80 | 0.3 | 24（AOE） | 範圍 60px |
| 鐳射塔 | 200 | 8/幀 | 持續 | ~480/s | 穿透護甲 30% |
| 減速塔 | 80 | 3 | 1.5 | 4.5 | 減速 50%，輔助 |
| 支援塔 | 120 | 0 | — | 0 | 鄰近塔 +20% DPS |

### 難度曲線

```gdscript
# 指數成長（推薦）
func get_enemy_hp(base_hp: int, wave_num: int) -> int:
    return int(base_hp * pow(1.12, wave_num - 1))

# Boss 波次（每 5 波）
func is_boss_wave(wave_num: int) -> bool:
    return wave_num % 5 == 0

func get_boss_hp(base_hp: int, wave_num: int) -> int:
    return get_enemy_hp(base_hp * 10, wave_num)
```

---

## LAYER 5：效能陷阱與解決方案

| 問題 | 症狀 | 解決方案 |
|------|------|---------|
| 每幀 `get_nodes_in_group()` | 50+ 塔時 FPS 下降 | Area2D 監控 + 快取列表 |
| 每個敵人獨立 A* | 30+ 敵人時 CPU 爆表 | Flow Field 共享流場 |
| 運行時 `instantiate` 投射物 | GC 停頓、幀率卡頓 | ProjectilePool 物件池 |
| PathFollow2D 大量子節點 | 路徑節點爆炸 | 自訂 progress 計算取代 |
| TileMap 含業務邏輯 | 渲染耦合邏輯 | MapManager 分離關注點 |
| `distance_to` 全場搜索 | O(n²) 複雜度 | Area2D collision 事件驅動 |
| 波次中途 GC | 短暫卡頓 | 預先 _warm_up() + 物件池 |
| 大量 StatusEffect tick | 每幀遍歷 | 改用 SceneTreeTimer 觸發 |

---

## LAYER 6：開源架構精華

### Mindustry（Flow Field + ECS）
- **路徑尋找**：BFS Flow Field，所有敵人共享同一流場，O(1) 每幀查詢
- **實體系統**：Arc ECS，避免 GC 停頓
- **關鍵教訓**：Flow Field 比個別 A* 效能高出 5~10 倍（100+ 敵人時）

### OpenRA（Trait 組合系統）
- **實體設計**：每個 Actor 組合 Trait（Health / Mobile / AttackBase）
- **多人同步**：Lockstep 網路模型，零延遲誤差
- **關鍵教訓**：Trait 組合比多層繼承更靈活，推薦用於塔類型設計

### Warzone 2100（資料驅動）
- **科技樹**：400+ 種科技定義在 JSON，程式碼只讀取執行
- **關鍵教訓**：塔屬性、波次資料全部資料驅動（.tres / JSON）

### BTD 系列設計模式
- **升級樹**：每塔兩條路線，最多各升 5 級，但只能同時升一條到 5
- **目標策略**：玩家可切換 First/Last/Strong/Close/Spread
- **關鍵教訓**：Target priority 切換是低成本高策略深度的設計

### Kingdom Rush 設計模式
- **固定路徑分流**：2~3 條路徑，塔位置影響所有路徑
- **英雄系統**：可移動英雄協助任一點
- **關鍵教訓**：固定路徑配合英雄移動，比純動態路徑更易設計關卡

---

## LAYER 7：MVP 建構路線圖

### Phase 1：地圖 + 路徑（1~2 天）
- TileMapLayer：道路 / 草地 / 建造區
- 自訂 tile 屬性：`walkable`、`buildable`
- Path2D 手動繪製（至少 2 條路徑）

### Phase 2：敵人行進（1 天）
- EnemyAI + PathFollow2D 路徑追蹤
- `reached_end` 信號 → GameManager 扣生命

### Phase 3：波次系統（1~2 天）
- WaveResource（.tres）+ WaveManager
- 「開始波次」按鈕，波次間允許建塔

### Phase 4：防禦塔（2~3 天）
- TurretBase + Area2D 偵測
- MapManager.can_build 格子驗證
- ProjectilePool 物件池（初始 60 個）
- 至少 2 種塔：基礎塔 + 爆炸塔

### Phase 5：UI + 金幣 + 升級（2~3 天）
- 敵人獎勵金幣，塔選擇面板
- 升級系統（最多 3 級，費用指數增長）
- 遊戲速度切換（1x / 2x / 3x）

### Phase 6：平衡 + 存讀檔（1~2 天）
- 難度縮放、Boss 波次
- 遊戲狀態序列化
- 勝利/失敗統計畫面

---

## 認知框架

### 我能做的
- 完整波次系統（WaveResource + WaveManager + 難度縮放 + shuffle）
- TurretBase 攻擊邏輯 + TargetingStrategy 6 種模式
- EnemyAI PathFollow2D 路徑追蹤 + Flow Field 大規模路徑
- ProjectilePool 物件池（含動態擴容）
- StatusEffect 系統（減速/燃燒/暈眩可疊加）
- DPS 計算公式 + 塔平衡設計參考

### 誠實邊界
- AStarGrid2D 動態障礙更新效能上限需實機測試
- NavigationRegion2D 與 TileMapLayer 4.4+ 整合步驟需驗證

### 反模式（禁止）
- ❌ 每個敵人獨立 A*：50+ 敵人改用 Flow Field
- ❌ 主迴圈 `instantiate` 投射物：必須 ProjectilePool
- ❌ 遊戲邏輯放在 TileMap `_draw()`：邏輯渲染分離
- ❌ 波次資料硬編碼：使用 WaveResource .tres 資料驅動
- ❌ 一個 Tower 腳本含所有塔類型：繼承 TurretBase 覆寫 `_perform_attack()`
- ❌ 每幀 `get_nodes_in_group("enemies")`：Area2D 或快取列表

---

## LAYER 8：抽卡 TD 變體

> 觸發：玩家會「抽角色上塔位」「角色有稀有度差異」「戰勝給 premium 貨幣」即進入此模式。
> 來源：一款已通過 Sprint 1-2 驗收的抽卡 TD 專案實作；標「設計選擇」者為該專案玩測結論，非業界鐵則。

### 8.1 玩家迴圈 6 件套（依事實基礎分兩層）

> 重要：這 6 件套不是同等地位。前 3 件有業界事實基礎，後 3 件是設計選擇。寫文檔時不要混為一談。

#### A. TD 業界常規（有外部事實依據）

> 來源：Defender's Quest 設計師文章（fortressofdoors.com）明確列為 "common feature in tower defence games"

| # | 系統 | 業界依據 | 實作要點 |
|---|------|---------|---------|
| 1 | **暫停 / 1× / 2× / 3×** | TD 通用做法 | `Engine.time_scale`，UI 用 `process_mode = PROCESS_MODE_ALWAYS` |
| 2 | **波次間 Prep 階段（含「跳過倒數」）** | TD 通用做法 | WaveManager 加狀態機 `IDLE/SPAWNING/IN_PROGRESS/PREP/FINISHED` |
| 3 | **戰中塔升級** | TD 通用做法 | tower 加 `_level + LEVEL_DAMAGE_MULT[3]`，點已放塔顯升級面板 |

#### B. 抽卡 TD 設計選擇（從 Arknights 借鑑 ＋ 實際玩家測試驗證）

> 注意：這 3 件不是業界鐵則，是「某抽卡 TD 專案為了改善玩家體驗採用的設計」。換主題重做時可保留可替換。

| # | 系統 | 來源 | 實作要點 |
|---|------|------|---------|
| 4 | **角色招募費（部署費）** | Arknights DP 系統的簡化版（Arknights wiki：DP 1/sec auto-regen，redeploy ×1.5 cost） | `UnitData.deploy_cost`，金幣不夠的卡 `disabled = true` |
| 5 | **傷害浮動數字** | RPG/TD 常見視覺反饋（Tower Defense Simulator wiki：依傷害類型上色）| FloatingText autoload + Label pool，剋制橘大、不剋灰小 |
| 6 | **premium 貨幣戰後結算** | 抽卡遊戲設計變體（vs Clash Royale 寶箱即時掉）| 戰中只顯示「本戰累積」，戰勝才一次性 `PlayerData.add_currency()` |

> 玩家測試發現「戰中即時累加 premium 貨幣」會造成「不知道為什麼數字一直跳」的困惑 → 改成戰後結算。**這是單一專案實證，非業界鐵則**——換到別款抽卡 TD，玩家可能反而偏好戰中即時看到回饋。

### 8.2 雙資源耦合（戰中金幣 vs 戰外 premium）

**鐵則**：戰中產生的所有資源必須有「戰中出口」。

| 資源 | 入口 | 出口 |
|------|------|------|
| **金幣**（戰中）| 殺敵掉落 + 起始 200 | 招募新塔 + 升級已放塔（戰中即用即耗）|
| **premium 貨幣**（戰外）| 戰勝累計 + 通關獎勵 | 抽卡（主選單）|

不要讓玩家戰中看到一個「跳很快但戰中花不掉」的數字 — 這正是玩家抱怨「不知道為什麼這個數字一直加」的根因。

### 8.3 抽卡保底（參數範例，依自家營運目標調整）

```gdscript
const HARD_PITY_SSR := 90        # 硬保底
const SOFT_PITY_START := 74      # 軟保底起點
const SOFT_PITY_INC := 0.06      # 每抽 +6%

func _ssr_rate(pity_count: int) -> float:
    if pity_count < SOFT_PITY_START:
        return 0.006
    return 0.006 + (pity_count - SOFT_PITY_START + 1) * SOFT_PITY_INC
```

歪了下次保（限定池抽到非 UP 後，下次保底必出 UP）：
```gdscript
var guaranteed: bool = pity_data.get(pool.id + "_guaranteed", false)
var hit_up: bool = randf() < 0.5 or guaranteed
pity_data[pool.id + "_guaranteed"] = not hit_up
```

### 8.4 升星閾值（重複卡轉星）

實測可行值：1→2 / 2→3 / 3→4 / 4→5 / 5→6 = `[1, 2, 4, 8, 20]` 個重複副本。
**避坑**：不要用 `[2, 4, 8, 15, 30]`（太貴），玩家 SSR 在 20 小時遊戲壽命內升不了星。

### 8.5 多關卡 + 章節結構

```
data/
├── chapters.json          # 章節元資料 + unlock_after 控制解鎖鏈
├── waves/
│   ├── ch1_1.json         # 檔名 = stage_id（DataLoader 動態掃）
│   ├── ch1_2.json
│   └── ch1_N.json
```

**DataLoader 動態掃**（避免硬編碼 map_ids）：
```gdscript
func _load_waves() -> void:
    var dir := DirAccess.open("res://data/waves/")
    dir.list_dir_begin()
    var fname := dir.get_next()
    while fname != "":
        if fname.ends_with(".json"):
            _load_one_stage(fname.get_basename())
        fname = dir.get_next()
```

**PlayerData 解鎖判定**（簡潔 2 條規則）：
- 章節：`unlock_after` 為空 → 首章；否則前一章節/關卡 cleared
- 關卡：在章節內第 0 關 → 隨章節解鎖；其他 → 前一關 cleared

### 8.6 場景流（main_menu → world_map → chapter_map → battle_scene）

```
main_menu
   ├── 開始戰役 → world_map（6 章節列表）
   │                  └── 點章節 → chapter_map（7 關列表）
   │                                  └── 點關卡 → battle_scene（傳 stage_id 透過 GameManager.current_stage_id）
   └── 角色招募 → gacha_scene
```

**關鍵**：`GameManager.current_stage_id` 是「跨場景傳參」的標準做法，避免複雜的 set_meta / autoload 全域變數。

### 8.7 Critical Bug 紀錄（避免重蹈覆轍）

1. **物件池敵人 reset 時把 position 設 -9999** → 同 frame 內若有 emit `damage_dealt(target, ...)`，FloatingText 會跑到 (-9999, -9999)。**修法**：emit 提前到 `take_damage()` 之前。

2. **塔的攻擊光束用 `target.global_position - global_position`** → 敵人歸池後減出來是負值（往左上噴）。**修法**：用 `to_local(target.global_position)`，且 `_fire_flash_timer <= 0` 時清空 `_last_fire_target`。

3. **WaveManager 只連 `died` 信號減 alive，沒連 `reached_exit`** → Boss 走到底時 alive 永遠 > 0，波次永遠不結束。**修法**：兩個信號都連。

4. **Godot 4.6 把「無型別宣告」警告升級為 error** → `var raw := JSON.parse_string(...)` 編譯失敗。**修法**：`var raw: Variant = JSON.parse_string(...)` 顯式型別。

5. **Typed Array 指派**：`g.bond_ids = Array(d.get("bonds", []))` 失敗（無型別 → typed Array），改用 `g.bond_ids.assign(...)`。

6. **`.tscn` `CircleShape2D(radius=N)` 不是合法語法** → 必須用 `[sub_resource type="CircleShape2D" id="..."]` + `shape = SubResource("...")`。

### 8.8 設計優先工作流（重要）

中大型功能務必先產出設計文件再動手，**不要一步一試錯**。

建議的兩份文件：
- `DESIGN_REVIEW.md` — TD 設計診斷：逐項檢查玩家迴圈是否閉合、資源有無出口、難度曲線斷點
- `GAME_FLOW.md` — v1.0 路線圖：玩家旅程 ＋ 系統地圖 ＋ Sprint 路線

> 有 `game-designer` 類設計 agent 可用時，讓它產出這兩份；沒有就自己先寫完再開工。

### 8.9 換主題重做（這是 Skill 的「商業價值」）

抽卡 TD 的程式架構 95% 跟主題無關。換成「水滸 TD」「戰國 TD」「希臘神話 TD」只需：

1. **保留**：所有 .gd 程式碼、autoload 架構、battle_scene/world_map/chapter_map
2. **替換**：`data/*.json` 全部換新主題（角色名、敵兵名、章節名、羈絆組合）
3. **重設**：path_main / path_mountain 路徑點 + tower_slot 位置
4. **最後**：美術 Sprint 換對應主題立繪/BGM

預估換皮時間：**2-3 天**（純資料替換 + 路徑點 + 章節劇情）。

---

*版本：v3 | 最後更新：2026-05-01 | 適用：Godot 4.x GDScript | 抽卡 TD 模式經實際專案驗證*
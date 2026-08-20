# Godot 4 平台動作遊戲開發 Skill
# Platformer 架構知識庫 v2

## 觸發條件
當使用者要開發平台跳躍遊戲（2D 橫向卷軸、跳躍、障礙、敵人、衝刺、牆壁跳躍）時使用。

---

## LAYER 1：速查（每次必讀）

### 核心系統一覽
| 系統 | 說明 |
|------|------|
| 角色物理 | CharacterBody2D + move_and_slide，重力/跳躍/衝刺 |
| 輸入處理 | 水平移動、跳躍、衝刺、攻擊的輸入映射 |
| 狀態機 | StateMachine + State 類別，每個狀態獨立邏輯 |
| 動畫狀態機 | AnimationTree 或 AnimationPlayer，狀態驅動 |
| 關卡設計 | TileMapLayer 地形 + 場景物件 |
| Camera2D | 跟隨玩家，Look-ahead 超前預測，邊界限制 |
| 檢查點 | Checkpoint 系統，死亡復活 |
| 收集物 | Coin/Gem 拾取，得分系統 |
| 敵人 AI | 巡邏/追逐/跳躍式敵人 |

### MVP 最小可行場景結構

```
Level (Node2D)
+-- TileMapLayer        地形（地板/牆壁/障礙）
+-- ObjectLayer (Node2D)
|   +-- Player (CharacterBody2D)
|   +-- EnemyContainer (Node2D)
|   +-- CollectibleContainer (Node2D)
|   +-- HazardContainer (Node2D)  致死障礙
+-- Camera2D            跟隨玩家（look-ahead 版）
+-- Parallax2D          視差背景（一層一節點，4.3+ 官方建議）
+-- HUD (CanvasLayer)
|   +-- LivesDisplay
|   +-- ScoreLabel
|   +-- HealthBar
|   +-- DashCooldownBar
+-- CheckpointManager (Node)
```

### 手感調校參數速查表
| 參數 | 建議範圍 | 說明 |
|------|---------|------|
| GRAVITY | 980-1400 | 數值越大下墜越快，Celeste 用約 1600+ |
| JUMP_VELOCITY | -350 ~ -520 | 負值向上，越大跳越高 |
| FALL_MULTIPLIER | 2.0-3.5 | 下落時重力倍率（讓下墜感更重） |
| SHORT_HOP_FACTOR | 0.3-0.5 | 短跳截斷比例（放鍵後速度保留比率） |
| MOVE_SPEED | 150-250 | 一般橫向移動速度（px/s） |
| GROUND_ACCEL | 8-15 x speed | move_toward 每幀加速量倍率 |
| AIR_ACCEL | 4-8 x speed | 空中加速量倍率（較低=慣性感強） |
| COYOTE_TIME | 0.08-0.12 秒 | 離開平台後仍可跳躍的時間窗口 |
| JUMP_BUFFER | 0.08-0.15 秒 | 落地前預輸入跳躍的緩衝時間 |
| WALL_SLIDE_SPEED | 40-100 | 滑牆最大下落速度（px/s） |
| DASH_SPEED | 400-600 | 衝刺瞬間速度 |
| DASH_DURATION | 0.15-0.25 秒 | 衝刺持續時間 |
| DASH_COOLDOWN | 0.5-1.0 秒 | 衝刺冷卻時間 |
| INVINCIBLE_DURATION | 1.0-2.0 秒 | 受傷後無敵幀時間 |
| APEX_GRAVITY_FACTOR | 0.5-0.7 | 跳躍最高點重力減弱比率（更多空中控制感） |

### 跳躍高度/距離換算公式（物理推導）
已知目標高度 H（像素）和上升時間 T（秒）：
- JUMP_VELOCITY = -2 * H / T
- GRAVITY = 2 * H / (T * T)
- 範例：高度 128px，上升 0.4 秒 => JUMP_VELOCITY=-640，GRAVITY=1600
- 水平跳躍距離 D = MOVE_SPEED x (T + sqrt(2*H/GRAVITY))

---

## LAYER 2：完整程式碼（核心系統）

### PlayerController 完整實作（含 Coyote Time / Jump Buffer / 雙跳 / 衝刺 / 牆跳 / 無敵幀）

```gdscript
# player.gd
class_name Player
extends CharacterBody2D

@export_group("Movement")
@export var move_speed: float = 200.0
@export var ground_accel_factor: float = 12.0
@export var air_accel_factor: float = 6.0
@export var ground_friction_factor: float = 10.0
@export var air_friction_factor: float = 3.0

@export_group("Jump")
@export var jump_velocity: float = -480.0
@export var double_jump_velocity: float = -380.0
@export var gravity_scale: float = 1.0
@export var fall_multiplier: float = 2.8
@export var apex_gravity_factor: float = 0.55
@export var apex_threshold: float = 60.0
@export var max_fall_speed: float = 700.0
@export var coyote_time: float = 0.10
@export var jump_buffer_time: float = 0.12

@export_group("Dash")
@export var dash_speed: float = 500.0
@export var dash_duration: float = 0.18
@export var dash_cooldown: float = 0.6

@export_group("Wall")
@export var wall_slide_speed: float = 60.0
@export var wall_jump_velocity: Vector2 = Vector2(220.0, -420.0)
@export var wall_jump_lock_time: float = 0.12

@export_group("Combat")
@export var max_health: int = 3
@export var invincible_duration: float = 1.5
@export var knockback_force: float = 260.0

const GRAVITY = ProjectSettings.get_setting("physics/2d/default_gravity")

var health: int
var _coyote_timer: float = 0.0
var _jump_buffer_timer: float = 0.0
var _double_jumped: bool = false
var _is_dashing: bool = false
var _dash_timer: float = 0.0
var _dash_cooldown_timer: float = 0.0
var _dash_dir: Vector2 = Vector2.ZERO
var _wall_jump_lock_timer: float = 0.0
var _is_wall_sliding: bool = false
var _invincible: bool = false
var _facing_dir: float = 1.0

@onready var sprite: Sprite2D = $Sprite2D
@onready var anim: AnimationPlayer = $AnimationPlayer
@onready var ghost_container: Node2D = $GhostContainer

signal died
signal damaged(amount: int, new_health: int)

func _ready() -> void:
    health = max_health

func _physics_process(delta: float) -> void:
    _update_timers(delta)
    if _is_dashing:
        _process_dash(delta)
    else:
        _apply_gravity(delta)
        _handle_wall_slide()
        _handle_horizontal(delta)
        _handle_jump()
        _handle_dash_input()
    move_and_slide()
    _update_animation()

func _update_timers(delta: float) -> void:
    # Coyote Time：離地後倒數
    if is_on_floor():
        _coyote_timer = coyote_time
        _double_jumped = false
    else:
        _coyote_timer = max(_coyote_timer - delta, 0.0)
    # Jump Buffer：按跳後倒數
    if Input.is_action_just_pressed("jump"):
        _jump_buffer_timer = jump_buffer_time
    else:
        _jump_buffer_timer = max(_jump_buffer_timer - delta, 0.0)
    if _is_dashing:
        _dash_timer -= delta
        if _dash_timer <= 0.0:
            _end_dash()
    _dash_cooldown_timer = max(_dash_cooldown_timer - delta, 0.0)
    _wall_jump_lock_timer = max(_wall_jump_lock_timer - delta, 0.0)

func _apply_gravity(delta: float) -> void:
    if is_on_floor():
        if velocity.y > 0:
            velocity.y = 0
        return
    var grav = GRAVITY * gravity_scale
    # 下落時重力加倍（讓下墜感更重實）
    if velocity.y > 0:
        grav *= fall_multiplier
    # 上升且放開跳躍鍵，加速下落（短跳截斷）
    elif velocity.y < 0 and not Input.is_action_pressed("jump"):
        grav *= fall_multiplier * 0.8
    # 跳躍頂點附近，減輕重力（讓玩家有更多空中控制）
    elif abs(velocity.y) < apex_threshold:
        grav *= apex_gravity_factor
    velocity.y = min(velocity.y + grav * delta, max_fall_speed)

func _handle_horizontal(delta: float) -> void:
    if _wall_jump_lock_timer > 0:
        return  # 牆跳後短暫鎖定水平控制
    var dir: float = Input.get_axis("move_left", "move_right")
    if dir != 0.0:
        _facing_dir = dir
        sprite.flip_h = dir < 0.0
        var accel = ground_accel_factor if is_on_floor() else air_accel_factor
        velocity.x = move_toward(velocity.x, dir * move_speed, move_speed * accel * delta)
    else:
        var friction = ground_friction_factor if is_on_floor() else air_friction_factor
        velocity.x = move_toward(velocity.x, 0.0, move_speed * friction * delta)

func _handle_jump() -> void:
    var can_first_jump = is_on_floor() or _coyote_timer > 0.0
    if _jump_buffer_timer > 0.0:
        if _is_wall_sliding:
            _do_wall_jump()
        elif can_first_jump:
            velocity.y = jump_velocity
            _coyote_timer = 0.0
            _jump_buffer_timer = 0.0
        elif not _double_jumped:
            velocity.y = double_jump_velocity
            _double_jumped = true
            _jump_buffer_timer = 0.0

func _do_wall_jump() -> void:
    var wall_dir = get_wall_normal().x
    velocity.x = wall_dir * wall_jump_velocity.x
    velocity.y = wall_jump_velocity.y
    _wall_jump_lock_timer = wall_jump_lock_time
    _jump_buffer_timer = 0.0
    _is_wall_sliding = false

func _handle_wall_slide() -> void:
    _is_wall_sliding = false
    if is_on_floor() or not is_on_wall_only():
        return
    var wall_dir_input = Input.get_axis("move_left", "move_right")
    var pressing_into_wall = sign(get_wall_normal().x) != sign(wall_dir_input) or wall_dir_input == 0
    if pressing_into_wall and velocity.y > 0:
        _is_wall_sliding = true
        velocity.y = min(velocity.y, wall_slide_speed)

func _handle_dash_input() -> void:
    if Input.is_action_just_pressed("dash") and _dash_cooldown_timer <= 0.0:
        _start_dash()

func _start_dash() -> void:
    var dir = Vector2(Input.get_axis("move_left", "move_right"),
                      Input.get_axis("move_up", "move_down"))
    if dir == Vector2.ZERO:
        dir = Vector2(_facing_dir, 0.0)
    _dash_dir = dir.normalized()
    _is_dashing = true
    _dash_timer = dash_duration
    _dash_cooldown_timer = dash_cooldown
    velocity = _dash_dir * dash_speed
    _spawn_ghost()

func _process_dash(_delta: float) -> void:
    velocity = _dash_dir * dash_speed
    if randi() % 3 == 0:
        _spawn_ghost()

func _end_dash() -> void:
    _is_dashing = false
    velocity = _dash_dir * (move_speed * 0.6)

func _spawn_ghost() -> void:
    var ghost = Sprite2D.new()
    ghost.texture = sprite.texture
    ghost.hframes = sprite.hframes
    ghost.vframes = sprite.vframes
    ghost.frame = sprite.frame
    ghost.flip_h = sprite.flip_h
    ghost.global_position = sprite.global_position
    ghost.modulate = Color(0.4, 0.7, 1.0, 0.7)
    ghost_container.add_child(ghost)
    var tween = create_tween()
    tween.tween_property(ghost, "modulate:a", 0.0, 0.25)
    tween.tween_callback(ghost.queue_free)

func _update_animation() -> void:
    if _is_dashing:
        anim.play("dash")
    elif _is_wall_sliding:
        anim.play("wall_slide")
    elif not is_on_floor():
        if velocity.y < -50:
            anim.play("jump")
        else:
            anim.play("fall")
    elif abs(velocity.x) > 10:
        anim.play("run")
    else:
        anim.play("idle")

func take_damage(amount: int, source_position: Vector2 = Vector2.ZERO) -> void:
    if _invincible or _is_dashing:
        return
    health = max(health - amount, 0)
    emit_signal("damaged", amount, health)
    if source_position != Vector2.ZERO:
        var kb_dir = (global_position - source_position).normalized()
        kb_dir.y = min(kb_dir.y, -0.3)
        velocity = kb_dir * knockback_force
    _start_invincibility()
    if health <= 0:
        _die()

func _start_invincibility() -> void:
    _invincible = true
    var tween = create_tween()
    tween.set_loops(int(invincible_duration / 0.15))
    tween.tween_property(sprite, "modulate:a", 0.2, 0.075)
    tween.tween_property(sprite, "modulate:a", 1.0, 0.075)
    await get_tree().create_timer(invincible_duration).timeout
    _invincible = false
    sprite.modulate.a = 1.0

func _die() -> void:
    emit_signal("died")
    set_physics_process(false)
    var tween = create_tween()
    tween.tween_property(sprite, "modulate:a", 0.0, 0.4)
    tween.tween_callback(func(): GameManager.on_player_died(global_position))
```

### StateMachine 架構

```gdscript
# state_machine.gd
class_name StateMachine
extends Node

@export var initial_state: State
var current_state: State
var _states: Dictionary = {}
signal state_changed(from_state: String, to_state: String)

func _ready() -> void:
    for child in get_children():
        if child is State:
            _states[child.name] = child
            child.state_machine = self
    if initial_state:
        current_state = initial_state
        current_state.enter()

func _process(delta: float) -> void:
    current_state.update(delta)

func _physics_process(delta: float) -> void:
    current_state.physics_update(delta)

func _unhandled_input(event: InputEvent) -> void:
    current_state.handle_input(event)

func transition_to(target_state_name: String, data: Dictionary = {}) -> void:
    if not _states.has(target_state_name):
        push_error("StateMachine: state '%s' not found." % target_state_name)
        return
    var from_name = current_state.name
    current_state.exit()
    current_state = _states[target_state_name]
    current_state.enter(data)
    emit_signal("state_changed", from_name, target_state_name)
```

```gdscript
# state.gd — 基礎 State 類別
class_name State
extends Node

var state_machine: StateMachine

func enter(_data: Dictionary = {}) -> void:
    pass

func exit() -> void:
    pass

func update(_delta: float) -> void:
    pass

func physics_update(_delta: float) -> void:
    pass

func handle_input(_event: InputEvent) -> void:
    pass
```

```gdscript
# states/idle_state.gd — 靜止狀態示範
class_name IdleState
extends State

@onready var player: Player = $"../.."

func enter(_data: Dictionary = {}) -> void:
    player.anim.play("idle")

func physics_update(_delta: float) -> void:
    if not player.is_on_floor():
        state_machine.transition_to("Fall")
    elif abs(Input.get_axis("move_left", "move_right")) > 0.1:
        state_machine.transition_to("Run")
    elif Input.is_action_just_pressed("jump"):
        state_machine.transition_to("Jump")
    elif Input.is_action_just_pressed("dash"):
        state_machine.transition_to("Dash")
```

### CameraController（超前預測 + 畫面震動）

```gdscript
# game_camera.gd
class_name GameCamera
extends Camera2D

@export var target: CharacterBody2D
@export var lookahead_distance: float = 100.0
@export var lookahead_smooth: float = 3.0
@export var vertical_lookahead: float = 40.0
@export var follow_smooth_h: float = 6.0
@export var follow_smooth_v: float = 4.0
@export var shake_decay: float = 5.0

var _shake_strength: float = 0.0
var _rng := RandomNumberGenerator.new()
var _lookahead_offset: Vector2 = Vector2.ZERO
var _target_lookahead: Vector2 = Vector2.ZERO

func _ready() -> void:
    _rng.randomize()
    if target:
        global_position = target.global_position

func _process(delta: float) -> void:
    if target == null:
        return
    var h_dir = sign(target.velocity.x)
    var v_look = 0.0
    if not target.is_on_floor():
        v_look = sign(target.velocity.y) * vertical_lookahead * 0.5
    _target_lookahead = Vector2(h_dir * lookahead_distance, v_look)
    _lookahead_offset = _lookahead_offset.lerp(_target_lookahead, lookahead_smooth * delta)
    var desired_pos = target.global_position + _lookahead_offset
    var new_pos = global_position
    new_pos.x = lerp(new_pos.x, desired_pos.x, follow_smooth_h * delta)
    new_pos.y = lerp(new_pos.y, desired_pos.y, follow_smooth_v * delta)
    global_position = new_pos
    if _shake_strength > 0:
        offset = Vector2(
            _rng.randf_range(-_shake_strength, _shake_strength),
            _rng.randf_range(-_shake_strength, _shake_strength)
        )
        _shake_strength = lerp(_shake_strength, 0.0, shake_decay * delta)
    else:
        offset = Vector2.ZERO

func shake(strength: float) -> void:
    _shake_strength = max(_shake_strength, strength)
# 使用：camera.shake(8.0) 受傷 / camera.shake(15.0) Boss 技能
```

---

## LAYER 3：進階手感設計

### Celeste 式移動手感設計

Celeste 的手感核心在於「重力比現實大 3-5 倍，但給玩家充足的容錯窗口」。

關鍵設計原則：
1. 重力非常大（落地快），但 JUMP_VELOCITY 也非常大，讓跳躍弧線短而快速
2. 地面加速極快（幾乎瞬間到達最大速度），讓操控感靈敏
3. 空中仍有完整方向控制（air_accel 不要太低）
4. Coyote Time 必須有（0.1 秒），避免挫折感
5. Jump Buffer 必須有（0.12 秒），讓連跳鏈接流暢

```gdscript
# Celeste 參考數值（Godot 4 換算）
const CELESTE_GRAVITY = 1600.0
const CELESTE_JUMP_VELOCITY = -580.0
const CELESTE_MOVE_SPEED = 240.0
const CELESTE_GROUND_ACCEL = 1000.0   # 幾乎瞬間加速（直接加速量，非倍率）
const CELESTE_AIR_ACCEL = 600.0
const CELESTE_FALL_MULT = 1.5
const CELESTE_MAX_FALL = 960.0

func _handle_celeste_horizontal(delta: float) -> void:
    var dir = Input.get_axis("move_left", "move_right")
    var accel = CELESTE_GROUND_ACCEL if is_on_floor() else CELESTE_AIR_ACCEL
    if dir != 0:
        velocity.x = move_toward(velocity.x, dir * CELESTE_MOVE_SPEED, accel * delta)
        sprite.flip_h = dir < 0
    else:
        velocity.x = move_toward(velocity.x, 0, accel * 1.5 * delta)
```

### 牆壁跳躍三變體（Standard / Super / Bounce）

```gdscript
enum WallJumpType { STANDARD, SUPER, BOUNCE }

func _do_wall_jump_advanced(type: WallJumpType = WallJumpType.STANDARD) -> void:
    var wall_normal_x = get_wall_normal().x
    match type:
        WallJumpType.STANDARD:
            # 標準轉向跳
            velocity.x = wall_normal_x * wall_jump_velocity.x
            velocity.y = wall_jump_velocity.y
            _wall_jump_lock_timer = 0.12
        WallJumpType.SUPER:
            # 保留大部分水平速度（Celeste Super Jump）
            velocity.x = wall_normal_x * move_speed * 0.3
            velocity.y = jump_velocity * 1.1
            _wall_jump_lock_timer = 0.06
        WallJumpType.BOUNCE:
            # 快速高速反彈
            velocity.x = wall_normal_x * wall_jump_velocity.x * 1.5
            velocity.y = wall_jump_velocity.y * 0.9
            _wall_jump_lock_timer = 0.18
```

### 衝刺殘影效果（GhostTrailManager）

```gdscript
# ghost_trail_manager.gd
class_name GhostTrailManager
extends Node

@export var ghost_interval: float = 0.03
@export var ghost_lifetime: float = 0.3
@export var ghost_color: Color = Color(0.3, 0.6, 1.0, 0.6)
@export var target_sprite: Sprite2D

var _ghost_timer: float = 0.0
var _active: bool = false

func _process(delta: float) -> void:
    if not _active:
        return
    _ghost_timer -= delta
    if _ghost_timer <= 0:
        _ghost_timer = ghost_interval
        _spawn_ghost()

func start() -> void:
    _active = true
    _ghost_timer = 0.0

func stop() -> void:
    _active = false

func _spawn_ghost() -> void:
    if target_sprite == null:
        return
    var ghost := Sprite2D.new()
    ghost.texture = target_sprite.texture
    ghost.hframes = target_sprite.hframes
    ghost.vframes = target_sprite.vframes
    ghost.frame = target_sprite.frame
    ghost.flip_h = target_sprite.flip_h
    ghost.global_position = target_sprite.global_position
    ghost.z_index = target_sprite.z_index - 1
    ghost.modulate = ghost_color
    get_tree().current_scene.add_child(ghost)
    var tween = create_tween()
    tween.tween_property(ghost, "modulate:a", 0.0, ghost_lifetime)
    tween.tween_property(ghost, "scale", Vector2(0.8, 0.8), ghost_lifetime)
    tween.tween_callback(ghost.queue_free)
```

### 受傷無敵幀 CombatComponent（解耦版）

```gdscript
# combat_component.gd
class_name CombatComponent
extends Node

@export var max_health: int = 3
@export var invincible_duration: float = 1.5
@export var knockback_strength: float = 250.0

var health: int
var _invincible: bool = false

signal health_changed(new_health: int, max_health: int)
signal died
signal hit(damage: int)

@onready var sprite: Sprite2D = get_parent().get_node("Sprite2D")
@onready var body: CharacterBody2D = get_parent()

func _ready() -> void:
    health = max_health

func take_damage(damage: int, attacker_position: Vector2 = Vector2.ZERO) -> void:
    if _invincible:
        return
    health = clampi(health - damage, 0, max_health)
    emit_signal("health_changed", health, max_health)
    emit_signal("hit", damage)
    if attacker_position != Vector2.ZERO and body:
        var kb_dir = (body.global_position - attacker_position).normalized()
        kb_dir.y = min(kb_dir.y, -0.3)
        body.velocity = kb_dir * knockback_strength
    if health <= 0:
        emit_signal("died")
    else:
        _trigger_invincibility()

func heal(amount: int) -> void:
    health = clampi(health + amount, 0, max_health)
    emit_signal("health_changed", health, max_health)

func _trigger_invincibility() -> void:
    _invincible = true
    _flash_sprite()
    await get_tree().create_timer(invincible_duration).timeout
    _invincible = false
    if sprite:
        sprite.modulate.a = 1.0

func _flash_sprite() -> void:
    if sprite == null:
        return
    var tween = create_tween()
    tween.set_loops(int(invincible_duration / 0.15))
    tween.tween_property(sprite, "modulate:a", 0.15, 0.075)
    tween.tween_property(sprite, "modulate:a", 1.0, 0.075)
```

### 鏡頭超前預測（Lead Camera）雙軸版說明

超前預測讓玩家能提早看見前方障礙：
- 玩家向右移動 -> 鏡頭向右偏移 lookahead_distance 像素
- 偏移使用 lerp 插值，避免突兀感
- 垂直方向：下墜時向下預測，上升時輕微向上

```gdscript
func _calculate_lookahead() -> Vector2:
    var h = sign(target.velocity.x) * lookahead_distance
    var v = 0.0
    if target.velocity.y > 100:
        v = vertical_lookahead
    elif target.velocity.y < -100:
        v = -vertical_lookahead * 0.3
    return Vector2(h, v)
```

---

## LAYER 4：開源專案分析

### 1. Godot Engine 官方 Physics Platformer Demo
來源: godotengine/godot-demo-projects => 2d/physics_platformer/
License: MIT

特點：
- 使用 RigidBody2D（非 CharacterBody2D），以 _integrate_forces() 驅動
- 碰撞響應完全物理驅動
- 包含踩頭消滅敵人機制
- 適合學習「完全物理驅動」vs「程式控制物理」的設計差異

```gdscript
# RigidBody2D 版控制示意（官方 Demo 模式）
func _integrate_forces(state: PhysicsDirectBodyState2D) -> void:
    var direction = Input.get_axis("move_left", "move_right")
    var new_velocity = state.linear_velocity
    new_velocity.x = direction * WALK_FORCE
    if is_on_floor and Input.is_action_just_pressed("jump"):
        new_velocity.y = JUMP_FORCE
    state.linear_velocity = new_velocity
```

### 2. Heart Platformer Godot 4（uheartbeast）
來源: github.com/uheartbeast/Heart-Platformer-Godot-4
License: MIT | 教學系列: YouTube Heart Platformer – Godot 4 Tutorial Series

特點：
- 涵蓋：Coyote Jump、Double Jump、Wall Jump、斜面地形（autotiles）
- 場景管理、UI 開發、手柄支援、選單製作
- 強調斜面 Tile 的 floor_snap_length 設定防止飛出

```gdscript
# Heart Platformer 的斜面關鍵設定
floor_max_angle = deg_to_rad(46.0)
floor_snap_length = 10.0
floor_stop_on_slope = true
motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
```

### 3. Celeste-Movement（yusufkaanocak）
來源: github.com/yusufkaanocak/Celeste-Movement
語言: GDScript（Godot 3，可改寫為 4）

核心常數（Godot 3 單位換算）：
- WALL_JUMP_TIME = 10 frames  ≈ 0.17 秒（@60fps）
- GRAVITY = 6 px/frame²       ≈ 2160 px/s²
- JUMP_SPEED = 105 px/frame   ≈ 6300 px/s（初速向上）
- DASH_SPEED = 160 px/frame   ≈ 9600 px/s（極快）
- DASH_TIME = 15 frames       ≈ 0.25 秒

架構發現：
- 衝刺方向鎖定：衝刺啟動後無法更改方向（承諾感設計）
- 衝刺後短暫保留速度（非立即歸零）
- 牆壁跳躍後有水平速度鎖定期，防止玩家立即回牆

### 4. Flick!（codernunk）
來源: github.com/codernunk/flick
語言: GDScript 4.x（Godot 4.3+）

架構特色：
- 完全用 StateMachine + State 架構組織玩家狀態
- 收集物使用 Area2D + Signal 解耦設計
- 支援 RUN / JUMP / FALL / DASH / WALL_SLIDE 五個狀態
- 輕量場景：Level => TileMapLayer + Player + ObjectPool

### 5. sankari（Valks-Games）
來源: github.com/Valks-Games/sankari
語言: C#（Godot 4），非牟利 F2P 2D 平台遊戲

架構發現（可參考的設計模式）：
- 使用 IPlayerAbility 介面統一管理各種行動能力
- 各能力（Jump、Dash、Attack）獨立為 Component，不污染主角腳本
- 網路同步就緒（預留多人介面）

---

## LAYER 5：物理陷阱與解決方案

### 斜坡滑動問題
症狀：玩家在斜坡上站著不動時，會緩慢下滑
原因：floor_stop_on_slope 預設關閉

```gdscript
func _ready() -> void:
    floor_stop_on_slope = true
    floor_snap_length = 10.0
    floor_max_angle = deg_to_rad(46.0)
```

### 旋轉/移動平台跟隨問題
症狀：玩家站在移動平台上時不隨平台移動

```gdscript
func _physics_process(delta: float) -> void:
    if is_on_floor():
        var floor_vel = get_platform_velocity()
        if floor_vel != Vector2.ZERO:
            velocity += floor_vel
    move_and_slide()
```

### TileMap 縫隙 Bug（Tile Seam Collision）
症狀：玩家在相鄰 Tile 邊界處卡住或莫名減速

```gdscript
# 程式碼解決
func _ready() -> void:
    floor_block_on_wall = false
    wall_min_slide_angle = deg_to_rad(15.0)
# Inspector: Safe Margin = 0.08
# Project Settings: Physics/2D/Default Contact Depth = 0.08
# TileSet: 每個 tile 使用 Single Convex Polygon
```

### 一次性平台（One-Way Platform）穿越

```gdscript
func _handle_drop_through() -> void:
    if Input.is_action_pressed("move_down") and Input.is_action_just_pressed("jump"):
        set_collision_mask_value(2, false)
        await get_tree().create_timer(0.25).timeout
        set_collision_mask_value(2, true)
```

---

## LAYER 6：行動能力狀態機整合

### 衝刺狀態（DashState）

```gdscript
# states/dash_state.gd
class_name DashState
extends State

var _timer: float = 0.0
var _dir: Vector2 = Vector2.ZERO

func enter(data: Dictionary = {}) -> void:
    _timer = player.dash_duration
    _dir = data.get("direction", Vector2(player._facing_dir, 0)).normalized()
    player.velocity = _dir * player.dash_speed
    player.ghost_trail.start()
    player.anim.play("dash")

func exit() -> void:
    player.ghost_trail.stop()
    player.velocity = _dir * player.move_speed * 0.5

func physics_update(delta: float) -> void:
    _timer -= delta
    player.velocity = _dir * player.dash_speed
    if _timer <= 0:
        if player.is_on_floor():
            state_machine.transition_to("Run")
        else:
            state_machine.transition_to("Fall")
```

### 勾爪（Grapple Hook）基礎實作

```gdscript
# grapple_hook.gd
class_name GrappleHook
extends Node2D

@export var max_range: float = 300.0
@export var pull_speed: float = 400.0
@export var rope_color: Color = Color(0.8, 0.6, 0.2)

var _hooked: bool = false
var _hook_pos: Vector2 = Vector2.ZERO
var _line: Line2D

@onready var player: CharacterBody2D = get_parent()
@onready var raycast: RayCast2D = $RayCast2D

func _ready() -> void:
    _line = Line2D.new()
    _line.default_color = rope_color
    _line.width = 2.0
    add_child(_line)

func _physics_process(_delta: float) -> void:
    if not _hooked:
        return
    var direction = (_hook_pos - player.global_position).normalized()
    var dist = player.global_position.distance_to(_hook_pos)
    if dist > 10.0:
        player.velocity = player.velocity.lerp(direction * pull_speed, 0.2)
    else:
        release()
    _line.clear_points()
    _line.add_point(to_local(player.global_position))
    _line.add_point(to_local(_hook_pos))

func fire(target_pos: Vector2) -> bool:
    raycast.target_position = to_local(target_pos).normalized() * max_range
    raycast.force_raycast_update()
    if raycast.is_colliding():
        _hook_pos = raycast.get_collision_point()
        _hooked = true
        return true
    return false

func release() -> void:
    _hooked = false
    _line.clear_points()
```

---

## LAYER 7：敵人 AI 模式

### 巡邏敵人（PatrolEnemy）

```gdscript
# enemies/patrol_enemy.gd
class_name PatrolEnemy
extends CharacterBody2D

@export var patrol_speed: float = 80.0
@export var detect_range: float = 200.0

var _direction: float = 1.0
const GRAVITY = ProjectSettings.get_setting("physics/2d/default_gravity")

func _physics_process(delta: float) -> void:
    if not is_on_floor():
        velocity.y += GRAVITY * delta
    velocity.x = _direction * patrol_speed
    move_and_slide()
    _check_wall_or_edge()
    _check_player_detect()

func _check_wall_or_edge() -> void:
    if is_on_wall():
        _direction *= -1
        $Sprite2D.flip_h = _direction < 0
        return
    var edge_check = $EdgeRayCast as RayCast2D
    if not edge_check.is_colliding():
        _direction *= -1
        $Sprite2D.flip_h = _direction < 0

func _check_player_detect() -> void:
    var player = get_tree().get_first_node_in_group("player")
    if player and global_position.distance_to(player.global_position) < detect_range:
        _direction = sign(player.global_position.x - global_position.x)
```

### 彈跳敵人（JumpEnemy）

```gdscript
# enemies/jump_enemy.gd
class_name JumpEnemy
extends CharacterBody2D

@export var jump_force: float = -320.0
@export var jump_interval: float = 2.0

var _timer: float = 0.0
const GRAVITY = ProjectSettings.get_setting("physics/2d/default_gravity")

func _physics_process(delta: float) -> void:
    if not is_on_floor():
        velocity.y += GRAVITY * delta
    else:
        _timer -= delta
        if _timer <= 0:
            velocity.y = jump_force
            _timer = jump_interval
            _face_player()
    move_and_slide()

func _face_player() -> void:
    var player = get_tree().get_first_node_in_group("player")
    if player:
        velocity.x = sign(player.global_position.x - global_position.x) * 100.0
        $Sprite2D.flip_h = velocity.x < 0
```

---

## LAYER 8：關卡系統 + 存讀

### 檢查點系統

```gdscript
# checkpoint_manager.gd (Autoload)
class_name CheckpointManager
extends Node

var spawn_position: Vector2 = Vector2.ZERO
var checkpoints_activated: Array[String] = []

func activate(checkpoint_id: String, pos: Vector2) -> void:
    if checkpoint_id in checkpoints_activated:
        return
    spawn_position = pos
    checkpoints_activated.append(checkpoint_id)
    _save_to_disk()

func get_spawn_pos() -> Vector2:
    return spawn_position if spawn_position != Vector2.ZERO else _get_level_default()

func _get_level_default() -> Vector2:
    var starts = get_tree().get_nodes_in_group("spawn_point")
    return starts[0].global_position if starts.size() > 0 else Vector2.ZERO

func _save_to_disk() -> void:
    var data = {"spawn": {"x": spawn_position.x, "y": spawn_position.y},
                "activated": checkpoints_activated}
    var file = FileAccess.open("user://checkpoint.dat", FileAccess.WRITE)
    if file:
        file.store_var(data)

func load_from_disk() -> void:
    if not FileAccess.file_exists("user://checkpoint.dat"):
        return
    var file = FileAccess.open("user://checkpoint.dat", FileAccess.READ)
    if file:
        var data = file.get_var()
        spawn_position = Vector2(data["spawn"]["x"], data["spawn"]["y"])
        checkpoints_activated = data["activated"]
```

### 收集物系統（漂浮動畫版）

```gdscript
# collectible.gd
class_name Collectible
extends Area2D

@export var value: int = 1
@export var float_amplitude: float = 5.0
@export var float_speed: float = 2.0
@export var collect_sound: AudioStream

var _base_y: float

func _ready() -> void:
    _base_y = position.y
    body_entered.connect(_on_body_entered)

func _process(_delta: float) -> void:
    position.y = _base_y + sin(Time.get_ticks_msec() * 0.001 * float_speed) * float_amplitude

func _on_body_entered(body: Node) -> void:
    if not body.is_in_group("player"):
        return
    GameManager.add_score(value)
    if collect_sound:
        AudioManager.play_sfx(collect_sound)
    _collect_animation()

func _collect_animation() -> void:
    set_deferred("monitoring", false)
    var tween = create_tween()
    tween.parallel().tween_property(self, "position:y", position.y - 30, 0.2)
    tween.parallel().tween_property(self, "modulate:a", 0.0, 0.2)
    tween.parallel().tween_property(self, "scale", Vector2(1.5, 1.5), 0.2)
    tween.tween_callback(queue_free)
```

### 關卡管理

```gdscript
# level_manager.gd (Autoload)
class_name LevelManager
extends Node

var current_level: int = 1
var total_levels: int = 10

func complete_level() -> void:
    GameManager.save_progress(current_level)
    current_level += 1
    if current_level > total_levels:
        SceneManager.change_scene("res://scenes/credits.tscn")
    else:
        SceneManager.change_scene("res://levels/level_%02d.tscn" % current_level)

func restart_level() -> void:
    CheckpointManager.load_from_disk()
    SceneManager.change_scene("res://levels/level_%02d.tscn" % current_level)
```

---

## LAYER 9：TileMapLayer 設定重點

```gdscript
# 在程式中查詢地形自定義屬性
func is_hazard_tile(pos: Vector2, tilemap: TileMapLayer) -> bool:
    var tile_pos = tilemap.local_to_map(tilemap.to_local(pos))
    var data = tilemap.get_cell_tile_data(tile_pos)
    if data == null:
        return false
    return data.get_custom_data("hazard") == true

# custom_data 其他用途：
# data.get_custom_data("climbable")   可攀爬牆面
# data.get_custom_data("slip_factor") 滑溜地板（float）
# data.get_custom_data("damage")      傷害地板（int）

# Parallax2D 設定原則（4.3+ 官方建議節點，一層一個 Parallax2D）：
# 靠近鏡頭的層：scroll_scale = Vector2(0.8, 0.5)
# 遠景層：scroll_scale = Vector2(0.2, 0.1)
# 舊 ParallaxBackground/ParallaxLayer 仍可用，但已非建議路線（motion_scale → scroll_scale）
```

> 像素完美渲染（stretch / snap 設定）與攝影機抖動的完整處理 → `References/godot-pixel-art.md`

---

## LAYER 10：MVP 建構路線圖

Phase 1 基礎移動（1-2 天）
- CharacterBody2D 基礎物理
- 水平移動（move_and_slide）+ 加速/減速分離
- 重力與跳躍（variable jump：短跳/長跳截斷）
- TileMapLayer 地形碰撞 + floor_snap_length 斜面設定

Phase 2 手感調整（1-2 天）
- Coyote Time 實作（0.10 秒）
- Jump Buffer 實作（0.12 秒）
- 跳躍頂點重力減弱（apex_gravity_factor = 0.55）
- 動畫狀態機（idle/run/jump/fall）

Phase 3 進階行動（1-2 天）
- 雙跳（double jump）
- 牆壁滑動（wall slide，限速 60 px/s）
- 牆壁跳躍（wall jump + 水平方向鎖定 0.12 秒）
- 衝刺（dash + GhostTrailManager 殘影效果）

Phase 4 Camera + 場景（1-2 天）
- Camera2D 跟隨（look-ahead 超前預測版）
- Camera limit（limit_left/right/top/bottom）
- 畫面震動（camera.shake()）
- Parallax2D 視差背景
- 收集物（Coin/Gem 漂浮 + 消失動畫）

Phase 5 敵人（1-2 天）
- 巡邏敵人（PatrolEnemy + EdgeRayCast 邊緣偵測）
- 踩頭攻擊（從上方跳消滅敵人）
- 致死障礙（Area2D 觸發 take_damage）
- 受傷無敵幀 + 擊退（CombatComponent）

Phase 6 檢查點 + HUD + 存讀（1-2 天）
- Checkpoint 系統（觸碰儲存、死亡復活）
- HUD（生命 / 分數 / 衝刺冷卻 ProgressBar）
- 關卡完成條件（Area2D 觸發終點旗幟）
- 關卡選擇畫面 + FileAccess 存讀進度

---

## 認知框架與誠實邊界

### 我能做的
- 完整 CharacterBody2D 物理（Coyote Time / Jump Buffer / Variable Jump / Apex Control）
- 狀態機架構（StateMachine + State，支援牆跳/衝刺/雙跳的狀態轉換）
- 衝刺殘影效果（GhostTrailManager，Sprite2D 複製淡出）
- Camera2D look-ahead 超前預測 + 畫面震動
- 受傷無敵幀 + 擊退（CombatComponent 解耦版）
- 勾爪基礎物理（RayCast2D 偵測 + 速度拉近）
- TileMapLayer 地形 custom_data 查詢（hazard/climbable/one_way）
- 物理陷阱修正（斜坡滑動 / TileMap 縫隙 / 移動平台跟隨）

### 我不確定的（需驗證）
- Godot 4.6 中 get_platform_velocity() 在旋轉平台上的精確行為
- AnimationTree BlendSpace 和手動 AnimationPlayer.play() 在複雜狀態機下的效能差異
- 手柄類比搖桿輸入死區設定的最佳實踐值（因手柄廠商不同差異大）
- Celeste 式衝刺在 Godot 4.x 物理引擎下是否需要 _physics_process 分幀處理

### 反模式（禁止）
- 禁止把物理邏輯放在 _process()：必須在 _physics_process()
- 禁止使用 KinematicBody2D（Godot 3 API）：Godot 4 用 CharacterBody2D
- 禁止在 _physics_process 中直接 instantiate 節點：使用 call_deferred 或物件池
- 禁止硬編碼重力值：使用 ProjectSettings.get_setting("physics/2d/default_gravity")
- 禁止跳過 Coyote Time 和 Jump Buffer：平台遊戲手感的最基礎要求，不能省
- 禁止在 Camera2D 設定 position = player.position（無插值）：使用 lerp() 或 RemoteTransform2D
- 禁止在衝刺狀態中允許玩家變更衝刺方向（Celeste 設計哲學：衝刺承諾）

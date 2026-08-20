# Godot 4 視覺小說開發完整指南 v2

> 版本：v2 | 日期：2026-04-19 | 適用：Godot 4.x + GDScript 4.x

---

## 目錄

1. [架構總覽](#架構總覽)
2. [DialogueEngine — 完整實作](#dialogueengine)
3. [CharacterManager — 5 槽位系統](#charactermanager)
4. [SceneDirector — 場景演出](#scenedirector)
5. [AudioManager — 雙軌交叉淡入](#audiomanager)
6. [SaveManager — 含縮圖壓縮](#savemanager)
7. [Dialogic 2 完整整合指南](#dialogic-2)
8. [Rakugo 框架分析](#rakugo)
9. [Godot vs Ren'Py 功能對比表](#godot-vs-renpy)
10. [多語言 i18n 實作指南](#i18n)
11. [開源工具分析](#開源工具分析)
12. [踩坑表格](#踩坑表格)
13. [專案結構建議](#專案結構)

---

## 架構總覽

```
視覺小說核心系統
├── Autoload（全域單例）
│   ├── DialogueEngine    ← 對話解析、條件跳轉、變量操作
│   ├── CharacterManager  ← 角色立繪管理（5 槽位）
│   ├── SceneDirector     ← 場景切換、演出特效
│   ├── AudioManager      ← BGM/SFX 雙軌管理
│   └── SaveManager       ← 存讀檔、縮圖壓縮
│
├── Scenes/
│   ├── GameMain.tscn     ← 遊戲主場景
│   ├── TitleScreen.tscn  ← 標題畫面
│   ├── SaveLoadScreen.tscn
│   └── CGGallery.tscn    ← CG 解鎖圖庫
│
├── Resources/
│   ├── dialogues/        ← .json 或 .dtl 對話檔
│   ├── characters/       ← 角色資料 Resource
│   ├── backgrounds/      ← 背景圖
│   └── cg/               ← CG 圖片（解鎖系統）
│
└── Scripts/              ← 所有 GDScript 腳本
```

### 訊號流程圖

```
玩家點擊
    ↓
DialogueEngine.advance()
    ↓
解析當前節點類型
    ├── DIALOGUE  → CharacterManager.show_emotion() + TextBox.type_text()
    ├── CHOICE    → ChoicePanel.show_choices()
    ├── CONDITION → 評估條件 → 跳轉分支
    ├── SET_VAR   → GameState.set_variable()
    ├── CG        → CGManager.unlock_and_show()
    └── JUMP      → 跳轉標籤
```

---

## DialogueEngine

完整實作，支援條件跳轉、變量操作、CG 解鎖。

```gdscript
# Scripts/DialogueEngine.gd
# Autoload 名稱：DialogueEngine
extends Node

# ─── 訊號 ───────────────────────────────────────────────
signal dialogue_started(script_id: String)
signal dialogue_ended
signal line_ready(line: DialogueLine)
signal choices_ready(choices: Array[ChoiceData])
signal variable_changed(key: String, value: Variant)
signal cg_unlocked(cg_id: String)
signal label_jumped(from_label: String, to_label: String)

# ─── 資料結構 ────────────────────────────────────────────
class DialogueLine:
    var character: String = ""
    var text: String = ""
    var emotion: String = "normal"
    var voice: String = ""
    var type: String = "DIALOGUE"  # DIALOGUE / NARRATION
    var commands: Array = []       # 附加指令列表

class ChoiceData:
    var text: String = ""
    var target_label: String = ""
    var condition: String = ""     # 條件表達式（空字串 = 無條件）
    var visible_always: bool = true  # false 時條件不符則隱藏

# ─── 內部狀態 ────────────────────────────────────────────
var _script_data: Dictionary = {}    # 載入的劇本資料
var _current_script_id: String = ""
var _nodes: Array = []               # 當前劇本節點列表
var _current_index: int = 0          # 當前節點索引
var _labels: Dictionary = {}         # label_name → index 映射
var _is_playing: bool = false
var _waiting_choice: bool = false
var _variables: Dictionary = {}      # 遊戲變量儲存

# ─── 常數 ────────────────────────────────────────────────
const SCRIPTS_PATH := "res://Resources/dialogues/"
const NODE_TYPES := {
    "DIALOGUE": "_handle_dialogue",
    "NARRATION": "_handle_narration",
    "CHOICE": "_handle_choice",
    "CONDITION": "_handle_condition",
    "SET_VAR": "_handle_set_var",
    "ADD_VAR": "_handle_add_var",
    "JUMP": "_handle_jump",
    "CG": "_handle_cg",
    "SCENE": "_handle_scene",
    "BGM": "_handle_bgm",
    "SFX": "_handle_sfx",
    "SHAKE": "_handle_shake",
    "FADE": "_handle_fade",
    "WAIT": "_handle_wait",
    "END": "_handle_end",
}

# ─── 公開 API ─────────────────────────────────────────────

func load_script(script_id: String) -> bool:
    """載入對話腳本（JSON 格式）"""
    var path := SCRIPTS_PATH + script_id + ".json"
    if not FileAccess.file_exists(path):
        push_error("[DialogueEngine] 找不到腳本：" + path)
        return false
    
    var file := FileAccess.open(path, FileAccess.READ)
    var json := JSON.new()
    var err := json.parse(file.get_as_text())
    file.close()
    
    if err != OK:
        push_error("[DialogueEngine] JSON 解析失敗：" + script_id)
        return false
    
    _script_data = json.data
    _nodes = _script_data.get("nodes", [])
    _current_script_id = script_id
    _current_index = 0
    _labels = {}
    
    # 建立標籤索引（預處理，避免跳轉時 O(n) 搜尋）
    for i in range(_nodes.size()):
        var node: Dictionary = _nodes[i]
        if node.has("label"):
            _labels[node["label"]] = i
    
    return true

func start(script_id: String, start_label: String = "") -> void:
    """開始播放對話"""
    if not load_script(script_id):
        return
    
    if start_label != "" and _labels.has(start_label):
        _current_index = _labels[start_label]
    
    _is_playing = true
    _waiting_choice = false
    dialogue_started.emit(script_id)
    _process_current_node()

func advance() -> void:
    """玩家點擊推進（跳過打字或進下一行）"""
    if not _is_playing or _waiting_choice:
        return
    
    # 若 TextBox 正在打字，先完成打字
    if GameMain.textbox.is_typing:
        GameMain.textbox.skip_typing()
        return
    
    _current_index += 1
    _process_current_node()

func select_choice(choice_index: int) -> void:
    """玩家選擇選項"""
    if not _waiting_choice:
        return
    
    var choice_node: Dictionary = _nodes[_current_index]
    var choices: Array = choice_node.get("choices", [])
    
    if choice_index < 0 or choice_index >= choices.size():
        push_error("[DialogueEngine] 無效選項索引：" + str(choice_index))
        return
    
    var selected: Dictionary = choices[choice_index]
    _waiting_choice = false
    
    # 跳轉至選項目標標籤
    var target: String = selected.get("jump", "")
    if target != "" and _labels.has(target):
        var from = _nodes[_current_index].get("label", "")
        _current_index = _labels[target]
        label_jumped.emit(from, target)
    else:
        _current_index += 1
    
    _process_current_node()

func jump_to_label(label_name: String) -> void:
    """強制跳轉到指定標籤"""
    if not _labels.has(label_name):
        push_error("[DialogueEngine] 找不到標籤：" + label_name)
        return
    var from := ""
    if _current_index < _nodes.size():
        from = _nodes[_current_index].get("label", "")
    _current_index = _labels[label_name]
    label_jumped.emit(from, label_name)
    _process_current_node()

func get_variable(key: String, default_value: Variant = null) -> Variant:
    return _variables.get(key, default_value)

func set_variable(key: String, value: Variant) -> void:
    _variables[key] = value
    variable_changed.emit(key, value)

func get_all_variables() -> Dictionary:
    return _variables.duplicate()

func load_variables(data: Dictionary) -> void:
    _variables = data.duplicate()

# ─── 私有：節點處理器 ─────────────────────────────────────

func _process_current_node() -> void:
    if _current_index >= _nodes.size():
        _handle_end({})
        return
    
    var node: Dictionary = _nodes[_current_index]
    var node_type: String = node.get("type", "DIALOGUE")
    
    if NODE_TYPES.has(node_type):
        call(NODE_TYPES[node_type], node)
    else:
        push_warning("[DialogueEngine] 未知節點類型：" + node_type)
        _current_index += 1
        _process_current_node()

func _handle_dialogue(node: Dictionary) -> void:
    # 執行附加指令（表情、位置等）
    _execute_commands(node.get("commands", []))
    
    var line := DialogueLine.new()
    line.character = node.get("character", "")
    line.text = _interpolate_variables(node.get("text", ""))
    line.emotion = node.get("emotion", "normal")
    line.voice = node.get("voice", "")
    line.type = "DIALOGUE"
    
    line_ready.emit(line)

func _handle_narration(node: Dictionary) -> void:
    _execute_commands(node.get("commands", []))
    
    var line := DialogueLine.new()
    line.character = ""
    line.text = _interpolate_variables(node.get("text", ""))
    line.type = "NARRATION"
    
    line_ready.emit(line)

func _handle_choice(node: Dictionary) -> void:
    _waiting_choice = true
    var raw_choices: Array = node.get("choices", [])
    var valid_choices: Array[ChoiceData] = []
    
    for raw in raw_choices:
        var cond: String = raw.get("condition", "")
        
        # 評估條件
        if cond != "" and not _evaluate_condition(cond):
            if not raw.get("visible_always", true):
                continue  # 條件不符且不強制顯示 → 隱藏
        
        var cd := ChoiceData.new()
        cd.text = _interpolate_variables(raw.get("text", ""))
        cd.target_label = raw.get("jump", "")
        cd.condition = cond
        cd.visible_always = raw.get("visible_always", true)
        valid_choices.append(cd)
    
    choices_ready.emit(valid_choices)

func _handle_condition(node: Dictionary) -> void:
    """條件跳轉節點"""
    var branches: Array = node.get("branches", [])
    
    for branch in branches:
        var cond: String = branch.get("condition", "")
        if cond == "" or _evaluate_condition(cond):
            var target: String = branch.get("jump", "")
            if target != "" and _labels.has(target):
                _current_index = _labels[target]
            else:
                _current_index += 1
            _process_current_node()
            return
    
    # 所有條件都不符合，執行 else 分支
    var else_jump: String = node.get("else", "")
    if else_jump != "" and _labels.has(else_jump):
        _current_index = _labels[else_jump]
    else:
        _current_index += 1
    _process_current_node()

func _handle_set_var(node: Dictionary) -> void:
    var key: String = node.get("key", "")
    var value: Variant = node.get("value", null)
    if key != "":
        set_variable(key, value)
    _current_index += 1
    _process_current_node()

func _handle_add_var(node: Dictionary) -> void:
    var key: String = node.get("key", "")
    var amount: float = float(node.get("amount", 0))
    var current: float = float(get_variable(key, 0))
    set_variable(key, current + amount)
    _current_index += 1
    _process_current_node()

func _handle_jump(node: Dictionary) -> void:
    var target: String = node.get("target", "")
    if target != "" and _labels.has(target):
        var from: String = node.get("label", "")
        _current_index = _labels[target]
        label_jumped.emit(from, target)
        _process_current_node()
    else:
        push_error("[DialogueEngine] JUMP 目標不存在：" + target)
        _current_index += 1
        _process_current_node()

func _handle_cg(node: Dictionary) -> void:
    var cg_id: String = node.get("cg_id", "")
    if cg_id != "":
        CGManager.unlock(cg_id)
        cg_unlocked.emit(cg_id)
        CGManager.show_fullscreen(cg_id)
    _current_index += 1
    # CG 顯示後等玩家點擊（由 CGManager 通知）

func _handle_scene(node: Dictionary) -> void:
    var bg_id: String = node.get("bg", "")
    var transition: String = node.get("transition", "crossfade")
    var duration: float = node.get("duration", 0.8)
    SceneDirector.change_background(bg_id, transition, duration)
    _current_index += 1
    _process_current_node()

func _handle_bgm(node: Dictionary) -> void:
    var track: String = node.get("track", "")
    var fade: float = node.get("fade", 1.5)
    AudioManager.play_bgm(track, fade)
    _current_index += 1
    _process_current_node()

func _handle_sfx(node: Dictionary) -> void:
    var clip: String = node.get("clip", "")
    AudioManager.play_sfx(clip)
    _current_index += 1
    _process_current_node()

func _handle_shake(node: Dictionary) -> void:
    var intensity: float = node.get("intensity", 5.0)
    var duration: float = node.get("duration", 0.3)
    SceneDirector.shake(intensity, duration)
    _current_index += 1
    _process_current_node()

func _handle_fade(node: Dictionary) -> void:
    var color: String = node.get("color", "black")
    var duration: float = node.get("duration", 1.0)
    var direction: String = node.get("direction", "in")  # in / out
    SceneDirector.fade(color, direction, duration)
    _current_index += 1
    # Fade 需等待完成，由 SceneDirector 訊號觸發繼續

func _handle_wait(node: Dictionary) -> void:
    var seconds: float = node.get("seconds", 1.0)
    await get_tree().create_timer(seconds).timeout
    _current_index += 1
    _process_current_node()

func _handle_end(_node: Dictionary) -> void:
    _is_playing = false
    _waiting_choice = false
    dialogue_ended.emit()

# ─── 輔助函式 ────────────────────────────────────────────

func _interpolate_variables(text: String) -> String:
    """將 {var_name} 替換為實際變量值"""
    var result := text
    var regex := RegEx.new()
    regex.compile(r"\{(\w+)\}")
    for match in regex.search_all(text):
        var var_name: String = match.get_string(1)
        var value: Variant = get_variable(var_name, "{" + var_name + "}")
        result = result.replace(match.get_string(), str(value))
    return result

func _evaluate_condition(expr: String) -> bool:
    """
    評估條件表達式
    支援格式：
      - "affection >= 50"
      - "flag_met_alice == true"
      - "route == \"good\""
      - "money > 100 and energy < 50"
    """
    # 替換變量值
    var processed := expr
    var regex := RegEx.new()
    regex.compile(r"\b([a-zA-Z_]\w*)\b")
    
    for match in regex.search_all(expr):
        var token: String = match.get_string()
        # 跳過運算子關鍵字
        if token in ["and", "or", "not", "true", "false"]:
            continue
        if _variables.has(token):
            var val: Variant = _variables[token]
            if val is String:
                processed = processed.replace(token, '"' + str(val) + '"')
            else:
                processed = processed.replace(token, str(val))
    
    # 使用 Godot 內建表達式求值
    var expression := Expression.new()
    var err := expression.parse(processed)
    if err != OK:
        push_error("[DialogueEngine] 條件解析失敗：" + expr)
        return false
    
    var result: Variant = expression.execute([], null, false)
    if expression.has_execute_failed():
        push_error("[DialogueEngine] 條件執行失敗：" + expr)
        return false
    
    return bool(result)

func _execute_commands(commands: Array) -> void:
    """執行節點附加指令"""
    for cmd in commands:
        match cmd.get("cmd", ""):
            "show_char":
                CharacterManager.show_character(
                    cmd.get("char_id", ""),
                    cmd.get("slot", 2),
                    cmd.get("emotion", "normal")
                )
            "hide_char":
                CharacterManager.hide_character(cmd.get("char_id", ""))
            "dim_others":
                CharacterManager.dim_all_except(cmd.get("char_id", ""))
            "move_char":
                CharacterManager.move_to_slot(
                    cmd.get("char_id", ""),
                    cmd.get("slot", 2)
                )
            _:
                push_warning("[DialogueEngine] 未知指令：" + str(cmd))
```

### 劇本 JSON 格式範例

```json
{
  "id": "chapter_01",
  "title": "相遇",
  "nodes": [
    { "label": "start", "type": "SET_VAR", "key": "affection_alice", "value": 0 },
    { "type": "SCENE", "bg": "school_gate", "transition": "fade_black", "duration": 1.0 },
    { "type": "BGM", "track": "morning_wind", "fade": 2.0 },
    {
      "type": "NARRATION",
      "text": "四月的早晨，陽光灑在校門前的石板路上。"
    },
    {
      "type": "DIALOGUE",
      "character": "alice",
      "emotion": "surprised",
      "text": "等等！你掉了東西！",
      "commands": [
        { "cmd": "show_char", "char_id": "alice", "slot": 3, "emotion": "surprised" }
      ]
    },
    {
      "type": "CHOICE",
      "choices": [
        { "text": "謝謝你。", "jump": "choice_polite" },
        { "text": "（假裝沒聽到）", "jump": "choice_ignore" },
        {
          "text": "（送她一個微笑）",
          "jump": "choice_smile",
          "condition": "charm >= 30",
          "visible_always": false
        }
      ]
    },
    {
      "label": "choice_polite",
      "type": "SET_VAR", "key": "affection_alice", "value": 5
    },
    {
      "type": "DIALOGUE",
      "character": "alice",
      "emotion": "happy",
      "text": "不客氣！我叫 Alice，你呢？"
    },
    { "type": "JUMP", "target": "continue" },
    {
      "label": "choice_ignore",
      "type": "DIALOGUE",
      "character": "alice",
      "emotion": "sad",
      "text": "...算了。"
    },
    { "type": "JUMP", "target": "continue" },
    {
      "label": "choice_smile",
      "type": "ADD_VAR", "key": "affection_alice", "amount": 10
    },
    {
      "type": "DIALOGUE",
      "character": "alice",
      "emotion": "blush",
      "text": "你…你的笑容好好看。"
    },
    {
      "label": "continue",
      "type": "CONDITION",
      "branches": [
        { "condition": "affection_alice >= 10", "jump": "good_end_flag" }
      ],
      "else": "neutral_continue"
    },
    {
      "label": "good_end_flag",
      "type": "SET_VAR", "key": "route_alice", "value": "good"
    },
    { "type": "JUMP", "target": "end_chapter" },
    {
      "label": "neutral_continue",
      "type": "SET_VAR", "key": "route_alice", "value": "neutral"
    },
    {
      "label": "end_chapter",
      "type": "CG",
      "cg_id": "cg_alice_meeting"
    },
    { "type": "END" }
  ]
}
```

---

## CharacterManager

5 槽位立繪系統，支援暗化、表情切換、動畫進場。

```gdscript
# Scripts/CharacterManager.gd
# Autoload 名稱：CharacterManager
extends Node

# ─── 訊號 ───────────────────────────────────────────────
signal character_shown(char_id: String, slot: int)
signal character_hidden(char_id: String)
signal emotion_changed(char_id: String, emotion: String)

# ─── 槽位設定 ────────────────────────────────────────────
# 螢幕寬 1280px，5 個槽位的 X 座標（百分比）
const SLOT_POSITIONS := {
    1: Vector2(0.1, 1.0),   # 最左
    2: Vector2(0.3, 1.0),   # 左中
    3: Vector2(0.5, 1.0),   # 正中
    4: Vector2(0.7, 1.0),   # 右中
    5: Vector2(0.9, 1.0),   # 最右
}

const SCREEN_SIZE := Vector2(1280, 720)
const CHAR_BASE_Y := 720.0            # 角色底部對齊螢幕底部
const APPEAR_DURATION := 0.3
const DISAPPEAR_DURATION := 0.25
const DIM_MODULATE := Color(0.5, 0.5, 0.5, 1.0)
const NORMAL_MODULATE := Color(1.0, 1.0, 1.0, 1.0)

# ─── 資料結構 ────────────────────────────────────────────
class CharacterSlot:
    var char_id: String = ""
    var slot_index: int = 0
    var sprite: Sprite2D = null
    var current_emotion: String = "normal"
    var is_dimmed: bool = false
    var tween: Tween = null

# ─── 內部狀態 ────────────────────────────────────────────
var _slots: Dictionary = {}          # slot_index → CharacterSlot
var _char_to_slot: Dictionary = {}   # char_id → slot_index
var _character_data: Dictionary = {} # 角色資料緩存
var _container: Node2D = null        # 立繪容器節點

# ─── 初始化 ──────────────────────────────────────────────

func _ready() -> void:
    # 找到場景中的立繪容器
    call_deferred("_init_container")

func _init_container() -> void:
    _container = get_tree().get_first_node_in_group("character_container")
    if not _container:
        push_error("[CharacterManager] 找不到 character_container 群組節點")

func load_character_data(char_id: String) -> Dictionary:
    """載入角色資料（含所有表情路徑）"""
    if _character_data.has(char_id):
        return _character_data[char_id]
    
    var path := "res://Resources/characters/" + char_id + ".json"
    if not FileAccess.file_exists(path):
        push_error("[CharacterManager] 找不到角色資料：" + path)
        return {}
    
    var file := FileAccess.open(path, FileAccess.READ)
    var json := JSON.new()
    json.parse(file.get_as_text())
    file.close()
    
    _character_data[char_id] = json.data
    return json.data

# ─── 公開 API ─────────────────────────────────────────────

func show_character(
    char_id: String,
    slot: int = 3,
    emotion: String = "normal",
    animate: bool = true
) -> void:
    """顯示角色立繪到指定槽位"""
    
    # 如果角色已在某槽位，先移除舊槽位記錄
    if _char_to_slot.has(char_id):
        var old_slot: int = _char_to_slot[char_id]
        if old_slot != slot:
            _clear_slot(old_slot)
    
    var char_data: Dictionary = load_character_data(char_id)
    if char_data.is_empty():
        return
    
    # 如果此槽位已有其他角色，先隱藏
    if _slots.has(slot) and _slots[slot].char_id != "" and _slots[slot].char_id != char_id:
        hide_character(_slots[slot].char_id, false)
    
    # 建立或取得槽位
    var cs: CharacterSlot
    if _slots.has(slot) and _slots[slot].char_id == char_id:
        cs = _slots[slot]
    else:
        cs = CharacterSlot.new()
        cs.char_id = char_id
        cs.slot_index = slot
        cs.sprite = Sprite2D.new()
        cs.sprite.name = "char_" + char_id
        _container.add_child(cs.sprite)
        _slots[slot] = cs
        _char_to_slot[char_id] = slot
    
    # 設置表情貼圖
    _set_emotion_texture(cs, char_data, emotion)
    
    # 計算位置
    var slot_ratio: Vector2 = SLOT_POSITIONS.get(slot, Vector2(0.5, 1.0))
    var target_x: float = SCREEN_SIZE.x * slot_ratio.x
    cs.sprite.position = Vector2(target_x, CHAR_BASE_Y)
    cs.sprite.visible = true
    
    # 進場動畫
    if animate:
        cs.sprite.modulate.a = 0.0
        _kill_tween(cs)
        cs.tween = create_tween()
        cs.tween.tween_property(cs.sprite, "modulate:a", 1.0, APPEAR_DURATION)
    else:
        cs.sprite.modulate.a = 1.0
    
    character_shown.emit(char_id, slot)

func hide_character(char_id: String, animate: bool = true) -> void:
    """隱藏指定角色"""
    if not _char_to_slot.has(char_id):
        return
    
    var slot: int = _char_to_slot[char_id]
    if not _slots.has(slot):
        return
    
    var cs: CharacterSlot = _slots[slot]
    
    if animate:
        _kill_tween(cs)
        cs.tween = create_tween()
        cs.tween.tween_property(cs.sprite, "modulate:a", 0.0, DISAPPEAR_DURATION)
        cs.tween.tween_callback(func(): _clear_slot(slot))
    else:
        _clear_slot(slot)
    
    character_hidden.emit(char_id)

func hide_all(animate: bool = true) -> void:
    """隱藏所有角色"""
    var ids := _char_to_slot.keys().duplicate()
    for char_id in ids:
        hide_character(char_id, animate)

func set_emotion(char_id: String, emotion: String) -> void:
    """切換角色表情（不改變位置）"""
    if not _char_to_slot.has(char_id):
        push_warning("[CharacterManager] 角色不在場：" + char_id)
        return
    
    var slot: int = _char_to_slot[char_id]
    var cs: CharacterSlot = _slots[slot]
    var char_data: Dictionary = load_character_data(char_id)
    
    _set_emotion_texture(cs, char_data, emotion)
    emotion_changed.emit(char_id, emotion)

func dim_all_except(active_char_id: String) -> void:
    """暗化所有角色，除了指定角色（強調說話者）"""
    for char_id in _char_to_slot.keys():
        var slot: int = _char_to_slot[char_id]
        var cs: CharacterSlot = _slots[slot]
        
        if char_id == active_char_id:
            _set_dim(cs, false)
        else:
            _set_dim(cs, true)

func undim_all() -> void:
    """恢復所有角色正常亮度"""
    for slot_idx in _slots.keys():
        _set_dim(_slots[slot_idx], false)

func move_to_slot(char_id: String, new_slot: int, animate: bool = true) -> void:
    """移動角色到新槽位"""
    if not _char_to_slot.has(char_id):
        return
    
    var old_slot: int = _char_to_slot[char_id]
    var cs: CharacterSlot = _slots[old_slot]
    
    var slot_ratio: Vector2 = SLOT_POSITIONS.get(new_slot, Vector2(0.5, 1.0))
    var target_x: float = SCREEN_SIZE.x * slot_ratio.x
    
    if animate:
        _kill_tween(cs)
        cs.tween = create_tween()
        cs.tween.tween_property(
            cs.sprite, "position:x", target_x, 0.4
        ).set_trans(Tween.TRANS_SINE)
    else:
        cs.sprite.position.x = target_x
    
    # 更新槽位記錄
    _slots.erase(old_slot)
    _slots[new_slot] = cs
    _char_to_slot[char_id] = new_slot
    cs.slot_index = new_slot

func get_active_characters() -> Array:
    return _char_to_slot.keys()

func is_character_visible(char_id: String) -> bool:
    return _char_to_slot.has(char_id)

# ─── 私有輔助 ────────────────────────────────────────────

func _set_emotion_texture(cs: CharacterSlot, char_data: Dictionary, emotion: String) -> void:
    var emotions: Dictionary = char_data.get("emotions", {})
    var tex_path: String = emotions.get(emotion, emotions.get("normal", ""))
    
    if tex_path == "":
        push_warning("[CharacterManager] 找不到表情：" + emotion)
        return
    
    var texture: Texture2D = load(tex_path)
    if texture:
        cs.sprite.texture = texture
        cs.current_emotion = emotion
    else:
        push_error("[CharacterManager] 貼圖載入失敗：" + tex_path)

func _set_dim(cs: CharacterSlot, dim: bool) -> void:
    if cs.is_dimmed == dim:
        return
    cs.is_dimmed = dim
    
    _kill_tween(cs)
    cs.tween = create_tween()
    var target_color: Color = DIM_MODULATE if dim else NORMAL_MODULATE
    cs.tween.tween_property(cs.sprite, "modulate", target_color, 0.2)

func _clear_slot(slot: int) -> void:
    if not _slots.has(slot):
        return
    var cs: CharacterSlot = _slots[slot]
    if cs.sprite and is_instance_valid(cs.sprite):
        cs.sprite.queue_free()
    _char_to_slot.erase(cs.char_id)
    _slots.erase(slot)

func _kill_tween(cs: CharacterSlot) -> void:
    if cs.tween and cs.tween.is_valid():
        cs.tween.kill()
        cs.tween = null
```

### 角色資料 JSON 格式

```json
{
  "id": "alice",
  "display_name": "Alice",
  "color": "#FF8CB4",
  "emotions": {
    "normal":    "res://Resources/characters/alice/alice_normal.png",
    "happy":     "res://Resources/characters/alice/alice_happy.png",
    "sad":       "res://Resources/characters/alice/alice_sad.png",
    "surprised": "res://Resources/characters/alice/alice_surprised.png",
    "angry":     "res://Resources/characters/alice/alice_angry.png",
    "blush":     "res://Resources/characters/alice/alice_blush.png",
    "thinking":  "res://Resources/characters/alice/alice_thinking.png"
  },
  "voice_prefix": "alice_",
  "default_slot": 3
}
```

---

## SceneDirector

場景演出系統，支援 crossfade、fade_black、shake。

```gdscript
# Scripts/SceneDirector.gd
# Autoload 名稱：SceneDirector
extends Node

# ─── 訊號 ───────────────────────────────────────────────
signal background_changed(bg_id: String)
signal fade_completed(direction: String)
signal shake_completed

# ─── 節點引用（由主場景設定）────────────────────────────
var background_layer: CanvasLayer = null
var bg_current: Sprite2D = null
var bg_next: Sprite2D = null
var fade_overlay: ColorRect = null
var shake_target: Node2D = null  # 整個場景的根節點

# ─── 狀態 ────────────────────────────────────────────────
var _current_bg_id: String = ""
var _is_transitioning: bool = false
var _shake_tween: Tween = null
var _fade_tween: Tween = null

const BG_PATH := "res://Resources/backgrounds/"

# ─── 初始化 ──────────────────────────────────────────────

func setup(bg_cur: Sprite2D, bg_nxt: Sprite2D, overlay: ColorRect, shake_root: Node2D) -> void:
    """由主場景呼叫，傳入必要節點"""
    bg_current = bg_cur
    bg_next = bg_nxt
    fade_overlay = overlay
    shake_target = shake_root
    fade_overlay.color = Color.BLACK
    fade_overlay.modulate.a = 0.0
    fade_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE

# ─── 公開 API ─────────────────────────────────────────────

func change_background(
    bg_id: String,
    transition: String = "crossfade",
    duration: float = 0.8
) -> void:
    """切換背景"""
    if bg_id == _current_bg_id:
        return
    
    var tex_path := BG_PATH + bg_id + ".png"
    var new_texture: Texture2D = load(tex_path)
    if not new_texture:
        push_error("[SceneDirector] 背景圖不存在：" + tex_path)
        return
    
    _is_transitioning = true
    
    match transition:
        "crossfade":
            await _crossfade(new_texture, duration)
        "fade_black":
            await _fade_through_black(new_texture, duration)
        "instant":
            bg_current.texture = new_texture
        "slide_left":
            await _slide_transition(new_texture, duration, Vector2(-1, 0))
        "slide_right":
            await _slide_transition(new_texture, duration, Vector2(1, 0))
        _:
            await _crossfade(new_texture, duration)
    
    _current_bg_id = bg_id
    _is_transitioning = false
    background_changed.emit(bg_id)

func fade(color_name: String, direction: String, duration: float) -> void:
    """淡入/淡出畫面"""
    var target_color: Color
    match color_name:
        "black": target_color = Color.BLACK
        "white": target_color = Color.WHITE
        "red":   target_color = Color(0.8, 0.0, 0.0)
        _:       target_color = Color.BLACK
    
    fade_overlay.color = target_color
    
    if _fade_tween and _fade_tween.is_valid():
        _fade_tween.kill()
    
    _fade_tween = create_tween()
    
    match direction:
        "in":   # 淡入 = 從透明到不透明
            fade_overlay.modulate.a = 0.0
            _fade_tween.tween_property(fade_overlay, "modulate:a", 1.0, duration)
        "out":  # 淡出 = 從不透明到透明
            fade_overlay.modulate.a = 1.0
            _fade_tween.tween_property(fade_overlay, "modulate:a", 0.0, duration)
    
    await _fade_tween.finished
    fade_completed.emit(direction)

func shake(intensity: float = 5.0, duration: float = 0.3, frequency: float = 30.0) -> void:
    """鏡頭震動"""
    if not shake_target:
        return
    
    var original_pos: Vector2 = shake_target.position
    
    if _shake_tween and _shake_tween.is_valid():
        _shake_tween.kill()
    
    var elapsed := 0.0
    var step := 1.0 / frequency
    
    _shake_tween = create_tween()
    
    while elapsed < duration:
        var decay: float = 1.0 - (elapsed / duration)
        var offset := Vector2(
            randf_range(-intensity, intensity) * decay,
            randf_range(-intensity, intensity) * decay
        )
        _shake_tween.tween_property(shake_target, "position", original_pos + offset, step)
        elapsed += step
    
    _shake_tween.tween_property(shake_target, "position", original_pos, step)
    await _shake_tween.finished
    shake_target.position = original_pos
    shake_completed.emit()

func flash(color: Color = Color.WHITE, duration: float = 0.15) -> void:
    """閃白/閃黑特效"""
    fade_overlay.color = color
    if _fade_tween and _fade_tween.is_valid():
        _fade_tween.kill()
    
    _fade_tween = create_tween()
    _fade_tween.tween_property(fade_overlay, "modulate:a", 1.0, duration * 0.2)
    _fade_tween.tween_property(fade_overlay, "modulate:a", 0.0, duration * 0.8)

func get_current_bg() -> String:
    return _current_bg_id

# ─── 私有：轉場動畫 ──────────────────────────────────────

func _crossfade(new_texture: Texture2D, duration: float) -> void:
    bg_next.texture = new_texture
    bg_next.modulate.a = 0.0
    bg_next.visible = true
    
    var tween := create_tween()
    tween.set_parallel(true)
    tween.tween_property(bg_next, "modulate:a", 1.0, duration)
    tween.tween_property(bg_current, "modulate:a", 0.0, duration)
    await tween.finished
    
    bg_current.texture = new_texture
    bg_current.modulate.a = 1.0
    bg_next.visible = false

func _fade_through_black(new_texture: Texture2D, duration: float) -> void:
    var half := duration * 0.5
    # 淡入黑色
    await fade("black", "in", half)
    # 切換背景
    bg_current.texture = new_texture
    # 淡出黑色
    await fade("black", "out", half)

func _slide_transition(new_texture: Texture2D, duration: float, direction: Vector2) -> void:
    var screen_w: float = SCREEN_SIZE.x if true else 1280.0
    bg_next.texture = new_texture
    bg_next.position = direction * screen_w
    bg_next.visible = true
    
    var tween := create_tween()
    tween.set_parallel(true)
    tween.tween_property(bg_next, "position", Vector2.ZERO, duration)\
        .set_trans(Tween.TRANS_SINE)
    tween.tween_property(bg_current, "position", -direction * screen_w, duration)\
        .set_trans(Tween.TRANS_SINE)
    await tween.finished
    
    bg_current.texture = new_texture
    bg_current.position = Vector2.ZERO
    bg_next.visible = false
```

---

## AudioManager

BGM 雙軌交叉淡入系統，支援同時播放環境音。

```gdscript
# Scripts/AudioManager.gd
# Autoload 名稱：AudioManager
extends Node

# ─── 訊號 ───────────────────────────────────────────────
signal bgm_changed(track_name: String)
signal sfx_played(clip_name: String)

# ─── 常數 ────────────────────────────────────────────────
const BGM_PATH   := "res://Resources/audio/bgm/"
const SFX_PATH   := "res://Resources/audio/sfx/"
const AMB_PATH   := "res://Resources/audio/ambient/"
const DEFAULT_BGM_VOLUME := -6.0    # dB
const DEFAULT_SFX_VOLUME := 0.0
const MAX_SFX_CHANNELS   := 8       # 同時 SFX 數量上限

# ─── 音軌節點 ────────────────────────────────────────────
var _bgm_a: AudioStreamPlayer = null    # 雙軌 A
var _bgm_b: AudioStreamPlayer = null    # 雙軌 B
var _amb_player: AudioStreamPlayer = null
var _sfx_pool: Array[AudioStreamPlayer] = []  # SFX 音效池

# ─── 狀態 ────────────────────────────────────────────────
var _active_bgm: String = ""    # 當前播放 BGM 名稱
var _use_track_a: bool = true   # 目前活躍音軌是 A
var _bgm_tween: Tween = null
var _amb_tween: Tween = null

# ─── 音量設定（線性 0.0~1.0）────────────────────────────
var _master_volume: float = 1.0
var _bgm_volume: float = 0.8
var _sfx_volume: float = 1.0
var _voice_volume: float = 1.0

func _ready() -> void:
    _setup_audio_players()

func _setup_audio_players() -> void:
    # BGM 雙軌
    _bgm_a = AudioStreamPlayer.new()
    _bgm_a.name = "BGM_A"
    _bgm_a.bus = "BGM"
    add_child(_bgm_a)
    
    _bgm_b = AudioStreamPlayer.new()
    _bgm_b.name = "BGM_B"
    _bgm_b.bus = "BGM"
    add_child(_bgm_b)
    
    # 環境音
    _amb_player = AudioStreamPlayer.new()
    _amb_player.name = "Ambient"
    _amb_player.bus = "Ambient"
    add_child(_amb_player)
    
    # SFX 音效池
    for i in range(MAX_SFX_CHANNELS):
        var sfx := AudioStreamPlayer.new()
        sfx.name = "SFX_" + str(i)
        sfx.bus = "SFX"
        add_child(sfx)
        _sfx_pool.append(sfx)

# ─── BGM 控制 ────────────────────────────────────────────

func play_bgm(track_name: String, crossfade_duration: float = 1.5) -> void:
    """播放 BGM（雙軌交叉淡入）"""
    if track_name == _active_bgm:
        return
    
    var path := BGM_PATH + track_name + ".ogg"
    if not FileAccess.file_exists(path):
        push_error("[AudioManager] BGM 不存在：" + path)
        return
    
    var new_stream: AudioStream = load(path)
    
    # 取得即將播放的音軌
    var incoming: AudioStreamPlayer = _bgm_b if _use_track_a else _bgm_a
    var outgoing: AudioStreamPlayer = _bgm_a if _use_track_a else _bgm_b
    
    incoming.stream = new_stream
    incoming.volume_db = linear_to_db(0.0)
    incoming.play()
    
    # 交叉淡入
    if _bgm_tween and _bgm_tween.is_valid():
        _bgm_tween.kill()
    
    _bgm_tween = create_tween()
    _bgm_tween.set_parallel(true)
    
    var target_db: float = linear_to_db(_bgm_volume * _master_volume)
    _bgm_tween.tween_property(incoming, "volume_db", target_db, crossfade_duration)
    
    if outgoing.playing:
        _bgm_tween.tween_property(
            outgoing, "volume_db",
            linear_to_db(0.001),  # 不能是 -inf，用近似靜音
            crossfade_duration
        )
        _bgm_tween.tween_callback(func(): outgoing.stop()).set_delay(crossfade_duration)
    
    _use_track_a = not _use_track_a
    _active_bgm = track_name
    bgm_changed.emit(track_name)

func stop_bgm(fade_duration: float = 1.0) -> void:
    """停止 BGM（帶淡出）"""
    var active: AudioStreamPlayer = _bgm_a if not _use_track_a else _bgm_b
    
    if _bgm_tween and _bgm_tween.is_valid():
        _bgm_tween.kill()
    
    _bgm_tween = create_tween()
    _bgm_tween.tween_property(active, "volume_db", linear_to_db(0.001), fade_duration)
    _bgm_tween.tween_callback(func(): active.stop())
    _active_bgm = ""

func pause_bgm() -> void:
    _bgm_a.stream_paused = true
    _bgm_b.stream_paused = true

func resume_bgm() -> void:
    _bgm_a.stream_paused = false
    _bgm_b.stream_paused = false

func get_current_bgm() -> String:
    return _active_bgm

# ─── SFX 控制 ────────────────────────────────────────────

func play_sfx(clip_name: String, volume_scale: float = 1.0) -> AudioStreamPlayer:
    """從音效池播放 SFX"""
    var path := SFX_PATH + clip_name + ".ogg"
    if not FileAccess.file_exists(path):
        # 嘗試 .wav
        path = SFX_PATH + clip_name + ".wav"
        if not FileAccess.file_exists(path):
            push_error("[AudioManager] SFX 不存在：" + clip_name)
            return null
    
    var player := _get_free_sfx_player()
    if not player:
        push_warning("[AudioManager] SFX 音效池已滿")
        return null
    
    player.stream = load(path)
    player.volume_db = linear_to_db(_sfx_volume * _master_volume * volume_scale)
    player.play()
    sfx_played.emit(clip_name)
    return player

func play_voice(voice_file: String) -> void:
    """播放語音（使用 Voice 音匯）"""
    var path := "res://Resources/audio/voice/" + voice_file
    if not FileAccess.file_exists(path):
        return
    
    var player := _get_free_sfx_player()
    if player:
        player.stream = load(path)
        player.volume_db = linear_to_db(_voice_volume * _master_volume)
        player.bus = "Voice"
        player.play()

# ─── 環境音 ──────────────────────────────────────────────

func play_ambient(amb_name: String, fade_duration: float = 2.0) -> void:
    var path := AMB_PATH + amb_name + ".ogg"
    if not FileAccess.file_exists(path):
        return
    
    if _amb_tween and _amb_tween.is_valid():
        _amb_tween.kill()
    
    _amb_player.stream = load(path)
    _amb_player.volume_db = linear_to_db(0.001)
    _amb_player.play()
    
    _amb_tween = create_tween()
    _amb_tween.tween_property(
        _amb_player, "volume_db",
        linear_to_db(0.5 * _master_volume),
        fade_duration
    )

func stop_ambient(fade_duration: float = 1.5) -> void:
    if _amb_tween and _amb_tween.is_valid():
        _amb_tween.kill()
    
    _amb_tween = create_tween()
    _amb_tween.tween_property(_amb_player, "volume_db", linear_to_db(0.001), fade_duration)
    _amb_tween.tween_callback(func(): _amb_player.stop())

# ─── 音量設定 ────────────────────────────────────────────

func set_master_volume(linear: float) -> void:
    _master_volume = clamp(linear, 0.0, 1.0)
    AudioServer.set_bus_volume_db(0, linear_to_db(_master_volume))

func set_bgm_volume(linear: float) -> void:
    _bgm_volume = clamp(linear, 0.0, 1.0)
    var db: float = linear_to_db(_bgm_volume)
    var bus_idx: int = AudioServer.get_bus_index("BGM")
    if bus_idx >= 0:
        AudioServer.set_bus_volume_db(bus_idx, db)

func set_sfx_volume(linear: float) -> void:
    _sfx_volume = clamp(linear, 0.0, 1.0)
    var bus_idx: int = AudioServer.get_bus_index("SFX")
    if bus_idx >= 0:
        AudioServer.set_bus_volume_db(bus_idx, linear_to_db(_sfx_volume))

func get_volume_settings() -> Dictionary:
    return {
        "master": _master_volume,
        "bgm": _bgm_volume,
        "sfx": _sfx_volume,
        "voice": _voice_volume,
    }

func load_volume_settings(data: Dictionary) -> void:
    set_master_volume(data.get("master", 1.0))
    set_bgm_volume(data.get("bgm", 0.8))
    set_sfx_volume(data.get("sfx", 1.0))
    _voice_volume = data.get("voice", 1.0)

# ─── 私有輔助 ────────────────────────────────────────────

func _get_free_sfx_player() -> AudioStreamPlayer:
    for player in _sfx_pool:
        if not player.playing:
            return player
    # 全部忙，強占最舊的
    return _sfx_pool[0]
```

---

## SaveManager

完整存讀檔系統，含縮圖壓縮與自動存檔。

```gdscript
# Scripts/SaveManager.gd
# Autoload 名稱：SaveManager
extends Node

# ─── 訊號 ───────────────────────────────────────────────
signal game_saved(slot: int)
signal game_loaded(slot: int)
signal save_failed(slot: int, reason: String)
signal auto_saved

# ─── 常數 ────────────────────────────────────────────────
const SAVE_DIR       := "user://saves/"
const SAVE_EXTENSION := ".sav"
const THUMB_EXTENSION:= ".png"
const MAX_SAVE_SLOTS := 20
const AUTO_SAVE_SLOT := 0           # 槽位 0 保留給自動存檔
const THUMB_WIDTH    := 240
const THUMB_HEIGHT   := 135         # 16:9 縮圖
const COMPRESS_QUALITY := 0.7       # JPG 品質（0.0~1.0）

# ─── 資料版本（升版時遷移用）────────────────────────────
const SAVE_VERSION := 2

# ─── 公開 API ─────────────────────────────────────────────

func _ready() -> void:
    DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SAVE_DIR))

func save_game(slot: int, caption: String = "") -> bool:
    """儲存遊戲到指定槽位"""
    if slot < 0 or slot > MAX_SAVE_SLOTS:
        save_failed.emit(slot, "槽位索引超出範圍")
        return false
    
    var save_data := _collect_save_data(caption)
    var json_str: String = JSON.stringify(save_data, "  ")
    
    var path: String = _get_save_path(slot)
    var file := FileAccess.open(path, FileAccess.WRITE)
    if not file:
        save_failed.emit(slot, "無法寫入檔案：" + path)
        return false
    
    file.store_string(json_str)
    file.close()
    
    # 儲存縮圖
    await _capture_and_save_thumbnail(slot)
    
    game_saved.emit(slot)
    return true

func load_game(slot: int) -> bool:
    """從指定槽位讀取遊戲"""
    var path: String = _get_save_path(slot)
    
    if not FileAccess.file_exists(path):
        push_error("[SaveManager] 存檔不存在：槽位 " + str(slot))
        return false
    
    var file := FileAccess.open(path, FileAccess.READ)
    var json := JSON.new()
    var err := json.parse(file.get_as_text())
    file.close()
    
    if err != OK:
        push_error("[SaveManager] 存檔解析失敗：槽位 " + str(slot))
        return false
    
    var data: Dictionary = json.data
    
    # 版本遷移
    data = _migrate_save_data(data)
    
    # 還原遊戲狀態
    _restore_game_state(data)
    
    game_loaded.emit(slot)
    return true

func auto_save() -> void:
    """自動存檔（槽位 0）"""
    await save_game(AUTO_SAVE_SLOT, "自動存檔")
    auto_saved.emit()

func delete_save(slot: int) -> bool:
    """刪除指定槽位存檔"""
    var path: String = _get_save_path(slot)
    var thumb_path: String = _get_thumb_path(slot)
    
    var deleted := false
    if FileAccess.file_exists(path):
        DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
        deleted = true
    if FileAccess.file_exists(thumb_path):
        DirAccess.remove_absolute(ProjectSettings.globalize_path(thumb_path))
    
    return deleted

func get_save_info(slot: int) -> Dictionary:
    """取得存檔摘要（不載入完整存檔）"""
    var path: String = _get_save_path(slot)
    if not FileAccess.file_exists(path):
        return {"exists": false}
    
    var file := FileAccess.open(path, FileAccess.READ)
    var json := JSON.new()
    json.parse(file.get_as_text())
    file.close()
    
    var data: Dictionary = json.data
    return {
        "exists": true,
        "slot": slot,
        "caption": data.get("caption", ""),
        "timestamp": data.get("timestamp", ""),
        "script_id": data.get("script_id", ""),
        "playtime": data.get("playtime", 0),
        "version": data.get("version", 1),
        "has_thumbnail": FileAccess.file_exists(_get_thumb_path(slot)),
    }

func get_all_save_infos() -> Array[Dictionary]:
    """取得所有槽位的存檔摘要"""
    var result: Array[Dictionary] = []
    for i in range(MAX_SAVE_SLOTS + 1):
        result.append(get_save_info(i))
    return result

func load_thumbnail(slot: int) -> ImageTexture:
    """載入槽位縮圖"""
    var path: String = _get_thumb_path(slot)
    if not FileAccess.file_exists(path):
        return null
    
    var img := Image.load_from_file(ProjectSettings.globalize_path(path))
    if not img:
        return null
    
    return ImageTexture.create_from_image(img)

func slot_exists(slot: int) -> bool:
    return FileAccess.file_exists(_get_save_path(slot))

# ─── 私有：資料收集 ──────────────────────────────────────

func _collect_save_data(caption: String) -> Dictionary:
    var now := Time.get_datetime_dict_from_system()
    var timestamp := "%04d-%02d-%02d %02d:%02d:%02d" % [
        now.year, now.month, now.day,
        now.hour, now.minute, now.second
    ]
    
    return {
        "version": SAVE_VERSION,
        "caption": caption,
        "timestamp": timestamp,
        "playtime": GameState.playtime,          # 遊戲時間（秒）
        
        # 對話進度
        "script_id": DialogueEngine._current_script_id,
        "node_index": DialogueEngine._current_index,
        "labels": DialogueEngine._labels,
        
        # 遊戲變量
        "variables": DialogueEngine.get_all_variables(),
        
        # 場景狀態
        "current_bg": SceneDirector.get_current_bg(),
        "current_bgm": AudioManager.get_current_bgm(),
        
        # 音量設定
        "volume": AudioManager.get_volume_settings(),
        
        # CG 解鎖記錄
        "unlocked_cgs": CGManager.get_unlocked_list(),
        
        # 已讀行（用於跳過已讀功能）
        "read_lines": GameState.get_read_lines(),
    }

func _restore_game_state(data: Dictionary) -> void:
    # 還原變量
    DialogueEngine.load_variables(data.get("variables", {}))
    
    # 還原音量
    AudioManager.load_volume_settings(data.get("volume", {}))
    
    # 還原 CG 解鎖
    CGManager.load_unlocked_list(data.get("unlocked_cgs", []))
    
    # 還原已讀記錄
    GameState.load_read_lines(data.get("read_lines", []))
    
    # 重新開始對話（從指定節點）
    var script_id: String = data.get("script_id", "")
    var node_index: int = data.get("node_index", 0)
    
    if script_id != "":
        DialogueEngine.load_script(script_id)
        DialogueEngine._current_index = node_index
        DialogueEngine._is_playing = true
        DialogueEngine._process_current_node()
    
    # 還原背景
    var bg: String = data.get("current_bg", "")
    if bg != "":
        SceneDirector.change_background(bg, "instant", 0.0)
    
    # 還原 BGM
    var bgm: String = data.get("current_bgm", "")
    if bgm != "":
        AudioManager.play_bgm(bgm, 0.0)

func _migrate_save_data(data: Dictionary) -> Dictionary:
    """版本遷移處理"""
    var ver: int = data.get("version", 1)
    
    if ver < 2:
        # v1 → v2：新增 read_lines 欄位
        data["read_lines"] = []
        data["version"] = 2
    
    return data

# ─── 私有：縮圖 ──────────────────────────────────────────

func _capture_and_save_thumbnail(slot: int) -> void:
    """截取當前畫面作為縮圖（壓縮儲存）"""
    await get_tree().process_frame
    await get_tree().process_frame  # 等兩幀確保畫面已更新
    
    var viewport: Viewport = get_tree().root
    var img: Image = viewport.get_texture().get_image()
    
    # 縮放至縮圖尺寸
    img.resize(THUMB_WIDTH, THUMB_HEIGHT, Image.INTERPOLATE_LANCZOS)
    
    # 儲存為 PNG（或 JPG 壓縮）
    var thumb_path: String = ProjectSettings.globalize_path(_get_thumb_path(slot))
    
    # 使用 JPG 壓縮節省空間（約 15~30KB vs PNG 100KB+）
    img.save_jpg(thumb_path, COMPRESS_QUALITY)

func _get_save_path(slot: int) -> String:
    return SAVE_DIR + "save_%02d" % slot + SAVE_EXTENSION

func _get_thumb_path(slot: int) -> String:
    return SAVE_DIR + "thumb_%02d" % slot + THUMB_EXTENSION
```

---

## Dialogic 2

完整整合指南，基於 Dialogic 2.x（Godot 4 版本）。

### 安裝步驟

```bash
# 方法 1：Asset Library（推薦）
# Godot 編輯器 → AssetLib → 搜尋 "Dialogic" → 安裝

# 方法 2：手動安裝
git clone https://github.com/coppolaemilio/dialogic.git
# 複製 addons/dialogic/ 到你的專案 addons/ 目錄
```

```gdscript
# project.godot 需要啟用插件
# 到 Project → Project Settings → Plugins → Dialogic 啟用
```

### 基本使用

```gdscript
# 啟動 Timeline（對話劇本）
func start_dialogue(timeline_name: String) -> void:
    var dialog_node = Dialogic.start(timeline_name)
    add_child(dialog_node)
    
    # 監聽事件
    Dialogic.timeline_ended.connect(_on_timeline_ended)
    Dialogic.signal_event.connect(_on_dialogic_signal)

func _on_timeline_ended() -> void:
    print("對話結束")

func _on_dialogic_signal(arg: String) -> void:
    # 從 Timeline 發出自定義訊號
    match arg:
        "open_shop":
            ShopManager.open()
        "unlock_cg_01":
            CGManager.unlock("cg_01")
```

### Dialogic 2 變量整合

```gdscript
# 讀取 Dialogic 內部變量
func get_dialogic_var(var_name: String) -> Variant:
    return Dialogic.VAR.get_variable(var_name)

func set_dialogic_var(var_name: String, value: Variant) -> void:
    Dialogic.VAR.set_variable(var_name, value)

# 範例：根據 Dialogic 變量決定劇情分支
func check_route() -> void:
    var affection: int = get_dialogic_var("affection_alice")
    if affection >= 50:
        Dialogic.start("route_alice_good")
    else:
        Dialogic.start("route_alice_neutral")
```

### 自訂事件（Custom Event）

```gdscript
# 建立自訂 Dialogic 事件
# 1. 在 addons/dialogic/Events/ 建立新資料夾
# 2. 繼承 DialogicEvent

class_name EventCGUnlock
extends DialogicEvent

var cg_id: String = ""

func _execute() -> void:
    CGManager.unlock(cg_id)
    CGManager.show_fullscreen(cg_id)
    # 等待玩家點擊再繼續
    await CGManager.cg_dismissed
    finish()

func _get_associated_script() -> String:
    return "res://addons/dialogic/Events/CG/event_cg_unlock.gd"
```

### Dialogic Style 系統（UI 客製化）

```gdscript
# Dialogic 2 使用 Style Resource 管理 UI
# 路徑：res://dialogic/styles/

# 在 Style 中設定：
# - Textbox 外觀（背景、字型、邊距）
# - 角色名稱顯示方式
# - 選項按鈕樣式
# - 全螢幕/半透明等版面

# 程式碼切換 Style
func switch_to_fullscreen_style() -> void:
    Dialogic.Styles.load_style("fullscreen_style")
```

### Dialogic Timeline 語法（.dtl 格式）

```
# 這是 Timeline 檔案格式（.dtl）
# 存放於 res://dialogic/timelines/

- character Alice: Hello, welcome!
- Alice (happy): I'm so glad you came!

- [if {affection_alice} >= 50]
  - Alice (blush): You mean a lot to me...
- [else]  
  - Alice (sad): We're not very close, are we...
- [end if]

- choice:
  "Give her a gift" -> alice_gift
  "Say goodbye" -> say_goodbye

= alice_gift
- Alice (surprised): For me?!
- [set affection_alice += 20]

= say_goodbye
- Alice: See you next time.

- [signal "check_ending"]
- [end]
```

---

## Rakugo

輕量替代框架分析。

### 特性概覽

- 基於 Godot 4，GDScript 撰寫
- 語法設計類似 Ren'Py 的 `define` / `say` 風格
- 專注純對話，無 Dialogic 的圖形 Timeline 編輯器
- 適合習慣程式化撰寫劇本的開發者

```gdscript
# Rakugo 基本語法
extends RakugoScene

func _scene() -> void:
    define("alice", "Alice", "#FF8CB4")
    define("narrator")
    
    narrator.say("春天的午後，校園裡很安靜。")
    alice.say("嗯哼～你在看什麼？", "curious")
    
    var choice = show_menu([
        "什麼都沒有",
        "在看你啊"
    ])
    
    if choice == 1:
        $ set_var("affection_alice", get_var("affection_alice") + 5)
        alice.say("哼！", "annoyed")
    else:
        alice.say("撒謊！", "playful")
```

### Rakugo vs 自製 DialogueEngine 比較

| 面向 | Rakugo | 自製 Engine |
|------|--------|-------------|
| 上手速度 | 快（有範例） | 慢（需自行設計） |
| 彈性 | 受框架限制 | 完全自由 |
| 維護依賴 | 依賴作者更新 | 自主掌控 |
| 效能 | 良好 | 依設計而定 |
| 社群支援 | 小型社群 | 無 |

---

## Godot vs Ren'Py

功能對比表（10 個維度）。

| 維度 | Godot 4 | Ren'Py |
|------|---------|--------|
| **學習曲線** | 中等（GDScript 自學）| 低（Python-like 語法，VN 特化）|
| **視覺小說語法** | 需自製或用 Dialogic | 原生支援（`say`、`menu`、`label`）|
| **角色立繪管理** | 需自行實作（彈性高）| 內建 `show character at left` |
| **存讀檔系統** | 需自行實作 | 原生自動存檔（多槽位）|
| **多語言（i18n）** | Godot 內建 Translation + CSV | 原生 `strings.rpy`，翻譯工具完善 |
| **動畫演出** | 完整 AnimationPlayer + Tween | 有限（ATL 語法）；複雜動畫困難 |
| **跨平台發布** | PC/Mobile/Web/Console（含 Switch）| PC/Mobile/Web；Console 支援有限 |
| **遊戲類型彈性** | 高（可做任何遊戲）| 低（VN 特化，非 VN 困難）|
| **自訂 UI** | 完全自由（Control 節點系統）| 受限（Screen 系統，客製化有學習成本）|
| **效能上限** | 高（原生引擎，可 3D）| 中（Python 基礎，重繪效能一般）|
| **CG 畫廊系統** | 需自行實作 | 內建 Gallery 模板（`image_gallery`）|
| **回退/歷史記錄** | 需自製 Rollback 系統 | 原生支援（Rollback 是核心功能）|
| **語音整合** | AudioStreamPlayer + 自訂 | 原生 `voice` 指令，自動對應行數 |
| **社群 VN 資源** | 少（Dialogic 為主）| 大量（Ren'Py 主流，資源豐富）|

### 建議選擇準則

- **選 Godot**：需要戰鬥系統、小遊戲、複雜動畫、精確 UI 控制，或未來要轉做非 VN 遊戲
- **選 Ren'Py**：純 VN、快速原型、初學者、需要原生 Rollback 和完整翻譯工具鏈

---

## i18n

多語言實作指南（Godot 4 內建 Translation 系統）。

### 翻譯檔案格式（CSV）

```csv
keys,zh_TW,zh_CN,en,ja
GREETING_ALICE,"嗨！很高興認識你。","嗨！很高兴认识你。","Hi! Nice to meet you.","こんにちは！よろしくね。"
CHOICE_ACCEPT,"好的，沒問題","好的，没问题","Sure, no problem","はい、いいですよ"
CHOICE_DECLINE,"抱歉，我沒辦法","抱歉，我没办法","Sorry, I can't","ごめん、できない"
CG_CAPTION_01,"第一次相遇","第一次相遇","First Meeting","初めての出会い"
UI_SAVE,"儲存","保存","Save","セーブ"
UI_LOAD,"讀取","读取","Load","ロード"
UI_SETTINGS,"設定","设置","Settings","設定"
```

### 導入 CSV 翻譯

```
Project Settings → Localization → Translations
→ Add → 選擇 .csv 檔案
→ Godot 自動生成 .translation 二進位檔
```

### GDScript 使用翻譯

```gdscript
# 取得翻譯文字
func tr_text(key: String) -> String:
    return tr(key)

# 切換語言
func set_language(locale: String) -> void:
    # 支援：zh_TW, zh_CN, en, ja
    TranslationServer.set_locale(locale)
    # 刷新所有顯示文字
    _refresh_all_ui()

func get_current_language() -> String:
    return TranslationServer.get_locale()

# 在 Label 節點中使用
func _refresh_all_ui() -> void:
    # 觸發 Control 節點重新讀取翻譯
    get_tree().call_group("localized_ui", "update_text")
```

### 對話系統整合 i18n

```gdscript
# 在 DialogueEngine 的 _handle_dialogue 中
func _handle_dialogue(node: Dictionary) -> void:
    var line := DialogueLine.new()
    var raw_text: String = node.get("text", "")
    
    # 如果 text 是翻譯 key（以 $ 開頭）
    if raw_text.begins_with("$"):
        line.text = tr(raw_text.substr(1))
    else:
        line.text = _interpolate_variables(raw_text)
    
    line_ready.emit(line)
```

### 劇本 JSON 多語言格式（兩種方案）

**方案 A：Key 引用（推薦，維護性高）**
```json
{
  "type": "DIALOGUE",
  "character": "alice",
  "text": "$SCENE01_LINE05"
}
```

**方案 B：多語言內嵌（小型專案）**
```json
{
  "type": "DIALOGUE",
  "character": "alice",
  "text": {
    "zh_TW": "你好啊！",
    "en": "Hello there!",
    "ja": "やあ！"
  }
}
```

```gdscript
# 方案 B 的解析程式碼
func _resolve_text(text_data: Variant) -> String:
    if text_data is String:
        return text_data
    if text_data is Dictionary:
        var locale: String = TranslationServer.get_locale()
        return text_data.get(locale, text_data.get("en", ""))
    return ""
```

### 字型設定（CJK 支援）

```gdscript
# 在 project.godot 中設定預設字型
# 或在 Control 節點的 Theme 中指定

# 推薦免費 CJK 字型：
# - Noto Sans CJK（Google）
# - Source Han Sans（Adobe）
# - Cubic 11（像素風格，含繁體中文）

# 字型回退設定（確保所有語言正確顯示）
func setup_font_fallback() -> void:
    var font := SystemFont.new()
    font.font_names = ["Noto Sans CJK TC", "Noto Sans", "Arial"]
    font.allow_system_fallback = true
```

### 語言設定存檔整合

```gdscript
# 在 SaveManager 中加入語言設定
func _collect_save_data(caption: String) -> Dictionary:
    var data := { ... }
    data["locale"] = TranslationServer.get_locale()
    return data

func _restore_game_state(data: Dictionary) -> void:
    var locale: String = data.get("locale", "zh_TW")
    TranslationServer.set_locale(locale)
    ...
```

---

## 開源工具分析

### 1. Dialogic 2

- **GitHub**：`coppolaemilio/dialogic`（4,000+ stars）
- **版本**：Dialogic 2.x（Godot 4 專用，與 Dialogic 1.x 不相容）
- **優點**：
  - 圖形化 Timeline 編輯器（無需寫 JSON）
  - 內建角色/立繪管理
  - 活躍社群，持續維護
  - 支援自訂事件擴充
- **缺點**：
  - 學習曲線：需了解其 Style 系統
  - 大型專案可能遇到效能問題（Timeline 節點過多）
  - 自訂 UI 需要了解 Dialogic Style Resource 架構
- **適合**：中型視覺小說、快速開發原型
- **踩坑**：Dialogic 1 → 2 無法直接遷移，需重寫所有 Timeline

### 2. Rakugo（Godot-Rakugo）

- **GitHub**：`rakugoteam/Rakugo-Dialogue-System`（800+ stars）
- **特性**：
  - 類 Ren'Py 語法，程式化撰寫
  - 輕量（無圖形編輯器）
  - GDScript 原生整合
- **適合**：熟悉 Ren'Py、偏好程式化工作流的開發者
- **不適合**：需要圖形 Timeline 的非程式師創作者

### 3. GodotVNE（Godot Visual Novel Engine）

- **特性**：
  - 完整 VN 框架，含存讀檔、回退、歷史記錄
  - 專為視覺小說設計
  - 含範例專案（適合學習架構）
- **限制**：Godot 4 版本相對較新，社群小
- **建議用法**：參考其架構設計，不建議直接依賴

### 各工具選擇建議

```
純 VN，快速開發   → Dialogic 2
程式化工作流      → Rakugo 或自製 Engine
複雜玩法混搭 VN   → 自製 Engine（本文實作）
學習 VN 架構      → 閱讀 GodotVNE 原始碼
```

---

## 踩坑表格

| # | 問題 | 症狀 | 原因 | 解法 |
|---|------|------|------|------|
| 1 | **Autoload 初始化順序** | `NullReferenceError`，Autoload A 呼叫 Autoload B 但 B 還沒 ready | Autoload 的 `_ready()` 執行順序依 Project Settings 列表順序 | 確保依賴關係正確排序；或改用 `call_deferred()` 延遲呼叫 |
| 2 | **Tween 未 kill 就重建** | 動畫衝突、卡頓、transform 跳動 | 舊 Tween 仍在執行，新 Tween 疊加干擾 | 每次建立新 Tween 前先 `old_tween.kill()`；統一用 class 成員變量管理 |
| 3 | **await 在 Autoload 失效** | `await signal` 之後程式不繼續 | Autoload 被 `queue_free()` 或場景切換後訊號來源消失 | 確認訊號發射方仍存活；改用 `timeout` 保護；或改成 callback 模式 |
| 4 | **JSON 劇本載入路徑錯誤** | `res://` 路徑在 export 後失效 | 未使用 PCK 打包，或路徑大小寫在 Linux/Android 不符 | 統一小寫路徑；使用 `FileAccess.file_exists()` 先驗證；確認匯出資源設定包含 `.json` |
| 5 | **BGM 交叉淡入爆音** | 新 BGM 剛播放時音量瞬間爆衝 | 初始 `volume_db` 設成 `0 dB`（線性 1.0）而非靜音 | `incoming.volume_db = linear_to_db(0.001)` 從近似靜音開始漸入；不要用 `-80` 因為 tween 結束前可能有閃音 |
| 6 | **存檔縮圖截圖時機** | 縮圖截到空畫面或上一幀畫面 | `get_texture().get_image()` 需要等 render 完成 | `await get_tree().process_frame` 兩次後再截圖；確保 Viewport 的 `render_target_update_mode` 正確 |
| 7 | **Expression 評估安全性** | 玩家輸入惡意表達式導致崩潰或執行任意程式碼 | 直接用 `Expression.execute()` 沒有沙箱 | 白名單過濾輸入；只允許劇本 JSON 中預設的條件格式；不讓玩家直接輸入條件表達式 |
| 8 | **角色立繪記憶體洩漏** | 長時間遊戲後 VRAM 持續上升 | 每次切換表情重新 `load()` 貼圖，舊貼圖未釋放 | 使用 `preload()` 在啟動時載入；或建立貼圖緩存 `Dictionary`，表情切換只改 `texture` 引用不重新載入 |
| 9 | **多語言 CSV 亂碼** | 繁體中文在某些系統顯示亂碼 | CSV 檔案儲存為非 UTF-8 編碼 | 確保 CSV 以 UTF-8 without BOM 儲存；Godot 的 Translation 系統預設 UTF-8 |
| 10 | **Dialogic 2 Style 衝突** | 自訂 UI 後 Dialogic 內建元素位置跑掉 | Style Resource 中的 Layout 與自訂場景節點重疊 | 在 Style 中設定 `base_scene` 為自訂場景；理解 Dialogic Layer 系統後再修改 |

---

## 專案結構

建議的完整 Godot 4 視覺小說專案目錄。

```
res://
├── addons/
│   └── dialogic/              ← Dialogic 2 插件（可選）
│
├── Autoloads/
│   ├── DialogueEngine.gd
│   ├── CharacterManager.gd
│   ├── SceneDirector.gd
│   ├── AudioManager.gd
│   ├── SaveManager.gd
│   ├── CGManager.gd           ← CG 解鎖管理
│   └── GameState.gd           ← 全域遊戲狀態（playtime 等）
│
├── Scenes/
│   ├── GameMain.tscn          ← 主場景（含 TextBox/CharContainer）
│   ├── TitleScreen.tscn
│   ├── SaveLoadScreen.tscn
│   ├── SettingsScreen.tscn
│   ├── CGGallery.tscn
│   └── UI/
│       ├── TextBox.tscn       ← 對話框（含打字機效果）
│       ├── ChoicePanel.tscn   ← 選項面板
│       ├── NamePlate.tscn     ← 角色名牌
│       └── BacklogPanel.tscn  ← 歷史對話記錄
│
├── Scripts/
│   ├── UI/
│   │   ├── TextBox.gd
│   │   ├── ChoiceButton.gd
│   │   └── BacklogEntry.gd
│   └── Utility/
│       ├── TypewriterEffect.gd
│       └── SaveSlotUI.gd
│
├── Resources/
│   ├── dialogues/             ← .json 劇本
│   │   ├── chapter_01.json
│   │   └── chapter_02.json
│   ├── characters/            ← 角色資料 JSON + 立繪圖片
│   │   ├── alice.json
│   │   └── alice/
│   │       ├── alice_normal.png
│   │       └── alice_happy.png
│   ├── backgrounds/           ← 背景圖（1280×720）
│   ├── cg/                    ← CG 圖片
│   ├── audio/
│   │   ├── bgm/               ← .ogg 格式
│   │   ├── sfx/               ← .ogg 或 .wav
│   │   ├── ambient/           ← 環境音
│   │   └── voice/             ← 語音
│   └── fonts/                 ← 字型（含 CJK）
│
├── Translations/
│   ├── strings.csv            ← 多語言翻譯表
│   └── strings.zh_TW.translation  ← 自動產生
│
└── project.godot
```

### project.godot Autoload 設定

```ini
[autoload]
GameState="*res://Autoloads/GameState.gd"
DialogueEngine="*res://Autoloads/DialogueEngine.gd"
CharacterManager="*res://Autoloads/CharacterManager.gd"
SceneDirector="*res://Autoloads/SceneDirector.gd"
AudioManager="*res://Autoloads/AudioManager.gd"
CGManager="*res://Autoloads/CGManager.gd"
SaveManager="*res://Autoloads/SaveManager.gd"
```

### TextBox 打字機效果（補充）

```gdscript
# Scripts/UI/TypewriterEffect.gd
extends RichTextLabel

signal typing_finished
signal character_typed(char: String)

var is_typing: bool = false
var _full_text: String = ""
var _chars_per_second: float = 40.0
var _tween: Tween = null

func type_text(text: String, speed: float = 40.0) -> void:
    _full_text = text
    _chars_per_second = speed
    visible_ratio = 0.0
    self.text = "[color=white]" + text + "[/color]"
    is_typing = true
    
    if _tween and _tween.is_valid():
        _tween.kill()
    
    var duration: float = float(text.length()) / _chars_per_second
    _tween = create_tween()
    _tween.tween_property(self, "visible_ratio", 1.0, duration)
    _tween.tween_callback(_on_typing_complete)

func skip_typing() -> void:
    if not is_typing:
        return
    if _tween and _tween.is_valid():
        _tween.kill()
    visible_ratio = 1.0
    _on_typing_complete()

func _on_typing_complete() -> void:
    is_typing = false
    typing_finished.emit()
```

---

> 本文件版本：**v2**
> 最後更新：2026-04-19
> 適用：Godot 4.x | GDScript 4.x | Dialogic 2.x
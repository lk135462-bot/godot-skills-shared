# Godot 4 RPG 開發完整指南 v2

> 版本：v2 | 語言：GDScript 4.x | 引擎：Godot 4.3+
> 更新日期：2026-04-19

---

## 觸發條件
當使用者要開發 RPG 遊戲（屬性系統、背包、任務追蹤、Buff/Debuff、裝備詞綴）時使用。

---

## LAYER 1：速查

### 核心系統一覽
| 系統 | 關鍵類別 | 說明 |
|------|---------|------|
| 屬性系統 | CharacterStats, CharacterStat, StatModifier | 加法/乘法/覆蓋三種 modifier，快取+dirty flag |
| 背包系統 | Inventory, ItemStack, EquipmentSlots | 個體 unique_id，穿脫自動套用 modifier |
| 任務系統 | QuestManager, QuestData, QuestCondition | 事件驅動，前置任務，存讀檔序列化 |
| Buff 系統 | BuffManager, BuffInstance, BuffData | REPLACE/REFRESH/STACK/INDEPENDENT 四種疊加策略 |
| 詞綴系統 | AffixGenerator, ItemAffix | 加權隨機，tier 分級，品質等級 |
| 事件匯流 | EventBus (AutoLoad) | Signal 中繼，解耦 UI 與邏輯 |

---

## LAYER 2：CharacterStats — 屬性 + Modifier 系統

### 設計原則
- **加法 modifier**：先疊加（扁平加成，如 +50 攻擊力）
- **乘法 modifier**：後套用（百分比，如 ×1.2）
- 公式：`FinalValue = (Base + SumAdditive) × Product(Multiplicative)`

### StatModifier

```gdscript
# stat_modifier.gd
class_name StatModifier
extends RefCounted

enum ModifierType { ADDITIVE, MULTIPLICATIVE, OVERRIDE }

var value    : float
var type     : ModifierType
var source   : String
var priority : int = 0

func _init(p_value: float, p_type: ModifierType, p_source: String = "", p_priority: int = 0) -> void:
    value = p_value; type = p_type; source = p_source; priority = p_priority
```

### CharacterStat — 單一屬性（含快取）

```gdscript
# character_stat.gd
class_name CharacterStat
extends RefCounted

signal value_changed(old_value: float, new_value: float)

var base_value: float:
    set(v):
        base_value = v
        _dirty = true
        _recalculate()

var _final_value : float = 0.0
var _dirty       : bool = true
var _modifiers   : Array[StatModifier] = []

func _init(base: float = 0.0) -> void:
    base_value = base

func get_value() -> float:
    if _dirty: _recalculate()
    return _final_value

func add_modifier(mod: StatModifier) -> void:
    _modifiers.append(mod)
    _modifiers.sort_custom(func(a, b): return a.priority < b.priority)
    _dirty = true
    _recalculate()

func remove_modifiers_from_source(source: String) -> void:
    var old_count = _modifiers.size()
    _modifiers = _modifiers.filter(func(m): return m.source != source)
    if _modifiers.size() != old_count:
        _dirty = true
        _recalculate()

func remove_modifier(mod: StatModifier) -> void:
    _modifiers.erase(mod)
    _dirty = true
    _recalculate()

func clear_modifiers() -> void:
    _modifiers.clear(); _dirty = true; _recalculate()

func _recalculate() -> void:
    var old_value = _final_value

    # Step 1：加法
    var additive_sum: float = 0.0
    for mod in _modifiers:
        if mod.type == StatModifier.ModifierType.ADDITIVE:
            additive_sum += mod.value

    # Step 2：乘法（獨立相乘）
    var multi_product: float = 1.0
    for mod in _modifiers:
        if mod.type == StatModifier.ModifierType.MULTIPLICATIVE:
            multi_product *= mod.value

    _final_value = (base_value + additive_sum) * multi_product

    # Step 3：Override
    for mod in _modifiers:
        if mod.type == StatModifier.ModifierType.OVERRIDE:
            _final_value = mod.value
            break

    _dirty = false
    if not is_equal_approx(old_value, _final_value):
        value_changed.emit(old_value, _final_value)
```

### CharacterStats — 角色屬性集合

```gdscript
# character_stats.gd
class_name CharacterStats
extends Resource

@export var max_hp               : float = 100.0
@export var max_mp               : float = 50.0
@export var base_attack          : float = 10.0
@export var base_defense         : float = 5.0
@export var base_speed           : float = 10.0
@export var base_critical_chance : float = 0.05
@export var base_critical_multiplier : float = 1.5

var hp                 : CharacterStat
var mp                 : CharacterStat
var attack             : CharacterStat
var defense            : CharacterStat
var speed              : CharacterStat
var critical_chance    : CharacterStat
var critical_multiplier: CharacterStat

var current_hp : float
var current_mp : float

func _init() -> void:
    hp                  = CharacterStat.new(max_hp)
    mp                  = CharacterStat.new(max_mp)
    attack              = CharacterStat.new(base_attack)
    defense             = CharacterStat.new(base_defense)
    speed               = CharacterStat.new(base_speed)
    critical_chance     = CharacterStat.new(base_critical_chance)
    critical_multiplier = CharacterStat.new(base_critical_multiplier)
    current_hp = hp.get_value()
    current_mp = mp.get_value()

func get_attack()  -> float: return attack.get_value()
func get_defense() -> float: return defense.get_value()

func calculate_damage_received(raw_damage: float) -> float:
    var mitigation = defense.get_value() / (defense.get_value() + 100.0)
    return raw_damage * (1.0 - mitigation)

func take_damage(amount: float) -> float:
    var actual = calculate_damage_received(amount)
    current_hp = maxf(0.0, current_hp - actual)
    return actual

func heal(amount: float) -> float:
    var before = current_hp
    current_hp = minf(hp.get_value(), current_hp + amount)
    return current_hp - before

func is_dead() -> bool: return current_hp <= 0.0

func add_modifier_to(stat_name: String, mod: StatModifier) -> void:
    var stat = _get_stat(stat_name)
    if stat: stat.add_modifier(mod)

func remove_modifiers_from(stat_name: String, source: String) -> void:
    var stat = _get_stat(stat_name)
    if stat: stat.remove_modifiers_from_source(source)

func _get_stat(stat_name: String) -> CharacterStat:
    match stat_name:
        "attack": return attack
        "defense": return defense
        "speed": return speed
        "hp": return hp
        "mp": return mp
        "critical_chance": return critical_chance
        "critical_multiplier": return critical_multiplier
    push_warning("CharacterStats: 未知屬性 " + stat_name)
    return null

func to_dict() -> Dictionary:
    return {
        "max_hp": max_hp, "max_mp": max_mp,
        "base_attack": base_attack, "base_defense": base_defense,
        "base_speed": base_speed,
        "current_hp": current_hp, "current_mp": current_mp,
    }

func from_dict(data: Dictionary) -> void:
    max_hp = data.get("max_hp", 100.0); max_mp = data.get("max_mp", 50.0)
    base_attack = data.get("base_attack", 10.0); base_defense = data.get("base_defense", 5.0)
    base_speed = data.get("base_speed", 10.0)
    current_hp = data.get("current_hp", max_hp); current_mp = data.get("current_mp", max_mp)
    hp.base_value = max_hp; mp.base_value = max_mp
    attack.base_value = base_attack; defense.base_value = base_defense
    speed.base_value = base_speed
```

---

## LAYER 3：InventorySystem

### ItemData — 物品資料

```gdscript
# item_data.gd
class_name ItemData
extends Resource

enum ItemType { CONSUMABLE, EQUIPMENT, MATERIAL, QUEST, KEY }
enum EquipSlot { NONE, WEAPON, ARMOR, HELMET, BOOTS, ACCESSORY_1, ACCESSORY_2 }

@export var id          : String = ""
@export var name        : String = ""
@export var description : String = ""
@export var icon        : Texture2D
@export var item_type   : ItemType = ItemType.MATERIAL
@export var equip_slot  : EquipSlot = EquipSlot.NONE
@export var max_stack   : int = 99
@export var sell_price  : int = 0
@export var buy_price   : int = 0
@export var weight      : float = 0.0
@export var base_modifiers : Dictionary = {}
@export var use_effect  : String = ""
```

### ItemStack — 物品堆疊（個體）

```gdscript
# item_stack.gd
class_name ItemStack
extends RefCounted

var item_data     : ItemData
var quantity      : int
var affixes       : Array[ItemAffix] = []
var enhance_level : int = 0
var unique_id     : String = ""

func _init(data: ItemData, qty: int = 1) -> void:
    item_data = data; quantity = qty
    unique_id = str(Time.get_ticks_usec()) + str(randi())

func can_stack_with(other: ItemStack) -> bool:
    if item_data.item_type == ItemData.ItemType.EQUIPMENT: return false
    return item_data.id == other.item_data.id

func add_quantity(amount: int) -> int:
    var added = mini(item_data.max_stack - quantity, amount)
    quantity += added; return added

func remove_quantity(amount: int) -> int:
    var removed = mini(quantity, amount)
    quantity -= removed; return removed

func is_empty() -> bool: return quantity <= 0

func get_all_modifiers() -> Array[Dictionary]:
    var result: Array[Dictionary] = []
    for stat_name in item_data.base_modifiers:
        result.append({"stat": stat_name, "value": item_data.base_modifiers[stat_name],
            "type": StatModifier.ModifierType.ADDITIVE, "source": unique_id})
    for affix in affixes:
        result.append_array(affix.get_modifiers(unique_id))
    return result
```

### Inventory — 背包

```gdscript
# inventory.gd
class_name Inventory
extends RefCounted

signal item_added(stack: ItemStack)
signal item_removed(stack: ItemStack, amount: int)
signal inventory_full()

var slots     : Array[ItemStack] = []
var max_slots : int = 40
var max_weight: float = 100.0

func get_current_weight() -> float:
    var w = 0.0
    for stack in slots:
        w += stack.item_data.weight * stack.quantity
    return w

func add_item(data: ItemData, quantity: int = 1) -> int:
    var remaining = quantity
    if data.item_type != ItemData.ItemType.EQUIPMENT:
        for stack in slots:
            if stack.item_data.id == data.id and stack.quantity < data.max_stack:
                remaining -= stack.add_quantity(remaining)
                item_added.emit(stack)
                if remaining <= 0: return 0
    while remaining > 0:
        if slots.size() >= max_slots:
            inventory_full.emit(); return remaining
        var new_stack = ItemStack.new(data, mini(remaining, data.max_stack))
        slots.append(new_stack)
        remaining -= new_stack.quantity
        item_added.emit(new_stack)
    return 0

func add_equipment_stack(stack: ItemStack) -> bool:
    if slots.size() >= max_slots:
        inventory_full.emit(); return false
    slots.append(stack); item_added.emit(stack); return true

func remove_item(item_id: String, quantity: int = 1) -> bool:
    var remaining = quantity
    var to_remove: Array[ItemStack] = []
    for stack in slots:
        if stack.item_data.id == item_id:
            remaining -= stack.remove_quantity(remaining)
            item_removed.emit(stack, mini(quantity, stack.quantity + remaining))
            if stack.is_empty(): to_remove.append(stack)
            if remaining <= 0: break
    for stack in to_remove: slots.erase(stack)
    return remaining <= 0

func remove_stack(stack: ItemStack) -> bool:
    if slots.has(stack):
        slots.erase(stack); item_removed.emit(stack, stack.quantity); return true
    return false

func get_item_count(item_id: String) -> int:
    var count = 0
    for stack in slots:
        if stack.item_data.id == item_id: count += stack.quantity
    return count

func has_item(item_id: String, quantity: int = 1) -> bool:
    return get_item_count(item_id) >= quantity

func sort_inventory() -> void:
    slots.sort_custom(func(a, b):
        if a.item_data.item_type != b.item_data.item_type:
            return a.item_data.item_type < b.item_data.item_type
        return a.item_data.name < b.item_data.name
    )
```

### EquipmentSlots — 裝備槽

```gdscript
# equipment_slots.gd
class_name EquipmentSlots
extends RefCounted

signal equipment_changed(slot: ItemData.EquipSlot, old_stack: ItemStack, new_stack: ItemStack)

var _slots: Dictionary = {
    ItemData.EquipSlot.WEAPON: null, ItemData.EquipSlot.ARMOR: null,
    ItemData.EquipSlot.HELMET: null, ItemData.EquipSlot.BOOTS: null,
    ItemData.EquipSlot.ACCESSORY_1: null, ItemData.EquipSlot.ACCESSORY_2: null,
}
var stats: CharacterStats

func _init(character_stats: CharacterStats) -> void:
    stats = character_stats

func equip(stack: ItemStack) -> ItemStack:
    var slot = stack.item_data.equip_slot
    if slot == ItemData.EquipSlot.NONE:
        push_error("此物品無法裝備"); return null
    var old_stack = _slots[slot]
    if old_stack != null: _remove_stack_modifiers(old_stack)
    _slots[slot] = stack
    _apply_stack_modifiers(stack)
    equipment_changed.emit(slot, old_stack, stack)
    return old_stack

func unequip(slot: ItemData.EquipSlot) -> ItemStack:
    var stack = _slots[slot]
    if stack == null: return null
    _remove_stack_modifiers(stack)
    _slots[slot] = null
    equipment_changed.emit(slot, stack, null)
    return stack

func get_equipped(slot: ItemData.EquipSlot) -> ItemStack:
    return _slots.get(slot, null)

func _apply_stack_modifiers(stack: ItemStack) -> void:
    for mod_data in stack.get_all_modifiers():
        var mod = StatModifier.new(mod_data["value"], mod_data["type"], mod_data["source"])
        stats.add_modifier_to(mod_data["stat"], mod)

func _remove_stack_modifiers(stack: ItemStack) -> void:
    for mod_data in stack.get_all_modifiers():
        stats.remove_modifiers_from(mod_data["stat"], mod_data["source"])
```

---

## LAYER 4：QuestManager

```gdscript
# quest_manager.gd
class_name QuestManager
extends Node

signal quest_started(quest: QuestData)
signal quest_completed(quest: QuestData)
signal quest_failed(quest: QuestData)
signal quest_updated(quest: QuestData, condition: QuestCondition)
signal quest_unlocked(quest: QuestData)

var _all_quests     : Dictionary = {}
var _quest_status   : Dictionary = {}
var _active_quests  : Array[QuestData] = []
var _completed_history : Array[String] = []
var _player         : Node

func initialize(player: Node, quest_database: Array[QuestData]) -> void:
    _player = player
    for quest in quest_database:
        _all_quests[quest.quest_id] = quest
        _quest_status[quest.quest_id] = QuestData.QuestStatus.LOCKED
    _evaluate_available_quests()

func _evaluate_available_quests() -> void:
    for quest_id in _all_quests:
        var quest: QuestData = _all_quests[quest_id]
        if _quest_status[quest_id] == QuestData.QuestStatus.LOCKED:
            if _check_prerequisites(quest):
                _quest_status[quest_id] = QuestData.QuestStatus.AVAILABLE
                quest_unlocked.emit(quest)

func _check_prerequisites(quest: QuestData) -> bool:
    for prereq_id in quest.prerequisites:
        if not _completed_history.has(prereq_id): return false
    return true

func start_quest(quest_id: String) -> bool:
    var status = _quest_status.get(quest_id, QuestData.QuestStatus.LOCKED)
    if status != QuestData.QuestStatus.AVAILABLE: return false
    var quest: QuestData = _all_quests[quest_id]
    _quest_status[quest_id] = QuestData.QuestStatus.ACTIVE
    for condition in quest.conditions: condition.reset()
    _active_quests.append(quest)
    quest_started.emit(quest)
    return true

func notify_event(condition_type: QuestData.ConditionType, target_id: String, amount: int = 1) -> void:
    for quest in _active_quests:
        for condition in quest.conditions:
            if condition.condition_type == condition_type and condition.target_id == target_id:
                condition.increment(amount)
                quest_updated.emit(quest, condition)
        if quest.auto_complete and _is_all_fulfilled(quest):
            complete_quest(quest.quest_id)

func complete_quest(quest_id: String) -> bool:
    var quest = _get_active_quest(quest_id)
    if quest == null or not _is_all_fulfilled(quest): return false
    _active_quests.erase(quest)
    _quest_status[quest_id] = QuestData.QuestStatus.COMPLETED
    _completed_history.append(quest_id)
    if quest.rewards: quest.rewards.apply_to(_player)
    if quest.repeatable:
        _quest_status[quest_id] = QuestData.QuestStatus.AVAILABLE
    quest_completed.emit(quest)
    _evaluate_available_quests()
    return true

func fail_quest(quest_id: String) -> void:
    var quest = _get_active_quest(quest_id)
    if quest == null: return
    _active_quests.erase(quest)
    _quest_status[quest_id] = QuestData.QuestStatus.FAILED
    quest_failed.emit(quest)

func _is_all_fulfilled(quest: QuestData) -> bool:
    for condition in quest.conditions:
        if not condition.is_fulfilled(): return false
    return true

func _get_active_quest(quest_id: String) -> QuestData:
    for quest in _active_quests:
        if quest.quest_id == quest_id: return quest
    return null

func save_state() -> Dictionary:
    var conditions_progress = {}
    for quest in _active_quests:
        conditions_progress[quest.quest_id] = quest.conditions.map(func(c): return c.current_amount)
    return {
        "quest_status": _quest_status.duplicate(),
        "active_quests": _active_quests.map(func(q): return q.quest_id),
        "completed_history": _completed_history.duplicate(),
        "conditions_progress": conditions_progress,
    }

func load_state(data: Dictionary) -> void:
    _quest_status = data.get("quest_status", {})
    _completed_history = data.get("completed_history", [])
    _active_quests.clear()
    var conditions_progress: Dictionary = data.get("conditions_progress", {})
    for quest_id in data.get("active_quests", []):
        if _all_quests.has(quest_id):
            var quest = _all_quests[quest_id]
            _active_quests.append(quest)
            if conditions_progress.has(quest_id):
                var amounts = conditions_progress[quest_id]
                for i in mini(amounts.size(), quest.conditions.size()):
                    quest.conditions[i].current_amount = amounts[i]
```

---

## LAYER 5：Buff/Debuff 系統

```gdscript
# buff_data.gd
class_name BuffData
extends Resource

enum StackBehavior { REPLACE, REFRESH, STACK, INDEPENDENT }

@export var buff_id         : String = ""
@export var buff_name       : String = ""
@export var duration        : float = 5.0
@export var tick_interval   : float = 0.0
@export var stack_behavior  : StackBehavior = StackBehavior.REPLACE
@export var max_stacks      : int = 1
@export var is_debuff       : bool = false
@export var stat_modifiers  : Array[Dictionary] = []
@export var tick_hp_change  : float = 0.0
```

```gdscript
# buff_manager.gd
class_name BuffManager
extends Node

signal buff_applied(instance: BuffInstance)
signal buff_removed(instance: BuffInstance)

var _buffs : Array[BuffInstance] = []
var _owner : Node

func _init(owner_node: Node) -> void: _owner = owner_node

func _process(delta: float) -> void:
    for buff in _buffs.duplicate(): buff.tick(delta)

func apply_buff(buff_data: BuffData, source: String) -> BuffInstance:
    match buff_data.stack_behavior:
        BuffData.StackBehavior.REPLACE:
            _remove_by_id(buff_data.buff_id)
            return _add_new(buff_data, source)
        BuffData.StackBehavior.REFRESH:
            var existing = _find_by_id(buff_data.buff_id)
            if existing: existing.refresh(); return existing
            return _add_new(buff_data, source)
        BuffData.StackBehavior.STACK:
            var existing = _find_by_id_and_source(buff_data.buff_id, source)
            if existing: existing.add_stack(); existing.refresh(); return existing
            return _add_new(buff_data, source)
        BuffData.StackBehavior.INDEPENDENT:
            return _add_new(buff_data, source)
    return _add_new(buff_data, source)

func _add_new(buff_data: BuffData, source: String) -> BuffInstance:
    var instance = BuffInstance.new(buff_data, source, _owner)
    instance.expired.connect(_on_buff_expired)
    instance.apply_modifiers()
    _buffs.append(instance)
    buff_applied.emit(instance)
    return instance

func remove_buff(buff_id: String, source: String = "") -> void:
    if source.is_empty(): _remove_by_id(buff_id)
    else: _remove_by_id_and_source(buff_id, source)

func _remove_by_id(buff_id: String) -> void:
    for buff in _buffs.duplicate():
        if buff.buff_data.buff_id == buff_id: _expire_buff(buff)

func _remove_by_id_and_source(buff_id: String, source: String) -> void:
    for buff in _buffs.duplicate():
        if buff.buff_data.buff_id == buff_id and buff.source == source: _expire_buff(buff)

func _expire_buff(instance: BuffInstance) -> void:
    instance.remove_modifiers()
    _buffs.erase(instance)
    buff_removed.emit(instance)

func _on_buff_expired(instance: BuffInstance) -> void: _expire_buff(instance)
func _find_by_id(buff_id: String) -> BuffInstance:
    for buff in _buffs:
        if buff.buff_data.buff_id == buff_id: return buff
    return null
func _find_by_id_and_source(buff_id: String, source: String) -> BuffInstance:
    for buff in _buffs:
        if buff.buff_data.buff_id == buff_id and buff.source == source: return buff
    return null
func has_buff(buff_id: String) -> bool: return _find_by_id(buff_id) != null
func clear_debuffs() -> void:
    for buff in _buffs.duplicate():
        if buff.buff_data.is_debuff: _expire_buff(buff)
```

---

## LAYER 6：裝備詞綴生成

```gdscript
# item_affix.gd
class_name ItemAffix
extends Resource

enum AffixType { PREFIX, SUFFIX }

@export var affix_id       : String = ""
@export var display_name   : String = ""
@export var affix_type     : AffixType
@export var tier           : int = 1
@export var weight         : int = 100
@export var modifier_ranges: Array[Dictionary] = []

var rolled_values: Array[float] = []

func roll() -> void:
    rolled_values.clear()
    for range_data in modifier_ranges:
        rolled_values.append(randf_range(range_data["min_value"], range_data["max_value"]))

func get_modifiers(source: String) -> Array[Dictionary]:
    var result: Array[Dictionary] = []
    for i in modifier_ranges.size():
        if i < rolled_values.size():
            result.append({
                "stat": modifier_ranges[i]["stat"],
                "value": rolled_values[i],
                "type": modifier_ranges[i].get("type", StatModifier.ModifierType.ADDITIVE),
                "source": source,
            })
    return result

func get_description() -> String:
    var parts = []
    for i in modifier_ranges.size():
        var v = rolled_values[i] if i < rolled_values.size() else 0.0
        parts.append("+%.1f %s" % [v, modifier_ranges[i]["stat"]])
    return ", ".join(parts)
```

```gdscript
# affix_generator.gd
class_name AffixGenerator
extends RefCounted

static var prefix_pool: Array[ItemAffix] = []
static var suffix_pool: Array[ItemAffix] = []

enum ItemRarity { NORMAL, MAGIC, RARE, LEGENDARY }

static func generate_item(base_item: ItemData, rarity: ItemRarity, item_level: int) -> ItemStack:
    var stack = ItemStack.new(base_item, 1)
    match rarity:
        ItemRarity.MAGIC:     _add_affixes(stack, 1, 1, item_level)
        ItemRarity.RARE:      _add_affixes(stack, 2, 2, item_level)
        ItemRarity.LEGENDARY: _add_affixes(stack, 3, 3, item_level)
    return stack

static func _add_affixes(stack: ItemStack, prefix_count: int, suffix_count: int, item_level: int) -> void:
    var max_tier = _level_to_max_tier(item_level)
    var eligible_p = prefix_pool.filter(func(a): return a.tier <= max_tier)
    var eligible_s = suffix_pool.filter(func(a): return a.tier <= max_tier)
    for affix in _weighted_sample(eligible_p, prefix_count) + _weighted_sample(eligible_s, suffix_count):
        var new_affix = affix.duplicate()
        new_affix.roll()
        stack.affixes.append(new_affix)

static func _level_to_max_tier(item_level: int) -> int:
    if item_level >= 60: return 5
    if item_level >= 40: return 4
    if item_level >= 25: return 3
    if item_level >= 10: return 2
    return 1

static func _weighted_sample(pool: Array[ItemAffix], count: int) -> Array[ItemAffix]:
    var result: Array[ItemAffix] = []
    var remaining = pool.duplicate()
    for _i in mini(count, remaining.size()):
        var total_weight = 0
        for a in remaining: total_weight += a.weight
        var roll = randi() % total_weight
        var cumulative = 0
        for j in remaining.size():
            cumulative += remaining[j].weight
            if roll < cumulative:
                result.append(remaining[j])
                remaining.remove_at(j)
                break
    return result

static func get_item_full_name(stack: ItemStack) -> String:
    var prefix_names = []; var suffix_names = []
    for affix in stack.affixes:
        if affix.affix_type == ItemAffix.AffixType.PREFIX: prefix_names.append(affix.display_name)
        else: suffix_names.append(affix.display_name)
    var name = stack.item_data.name
    if prefix_names.size() > 0: name = " ".join(prefix_names) + " " + name
    if suffix_names.size() > 0: name = name + " " + " ".join(suffix_names)
    return name
```

---

## LAYER 7：戰鬥系統類型比較

| 特性 | 即時戰鬥（ARPG）| 回合制（JRPG）| ATB |
|------|----------------|--------------|-----|
| 操作節奏 | 即時輸入 | 無時間壓力 | 有時間壓力但可暫停 |
| 實作複雜度 | 高 | 低 | 中 |
| 代表作 | Dark Souls, Hades | FF6, Persona | FF4-9, Chrono Trigger |

### ATB 計時系統

```gdscript
# atb_bar.gd
class_name ATBBar
extends RefCounted

signal ready(bar: ATBBar)

var progress    : float = 0.0
var max_progress: float = 100.0
var fill_rate   : float = 10.0
var is_ready    : bool = false

func tick(delta: float, speed_multiplier: float = 1.0) -> void:
    if is_ready: return
    progress += fill_rate * speed_multiplier * delta
    if progress >= max_progress:
        progress = max_progress
        is_ready = true
        ready.emit(self)

func consume() -> void: progress = 0.0; is_ready = false
```

---

## LAYER 8：數值平衡設計指南

```gdscript
# 等級曲線（指數）
static func exp_required(level: int) -> int:
    return int(100.0 * pow(level, 2.0))

# 傷害公式
static func calculate_damage(
    attacker_attack: float, defender_defense: float,
    skill_multiplier: float = 1.0, is_critical: bool = false,
    crit_multiplier: float = 1.5
) -> float:
    var mitigation = clampf(defender_defense / (defender_defense + 200.0), 0.0, 0.75)
    var base_damage = attacker_attack * skill_multiplier * (1.0 - mitigation)
    if is_critical: base_damage *= crit_multiplier
    return base_damage * randf_range(0.9, 1.1)

# 金幣掉落
static func calculate_gold_drop(enemy_level: int, player_level: int) -> int:
    var base = enemy_level * 5
    var level_diff = player_level - enemy_level
    if level_diff > 10: base = int(base * 0.3)
    elif level_diff > 5: base = int(base * 0.7)
    return base + randi() % int(base * 0.4)
```

### 平衡 QA 清單

| 檢查項目 | 目標 |
|---------|------|
| 1 級怪物秒殺 1 級玩家？ | 不可，預設 3-5 刀 |
| 滿等玩家 1 刀秒殺普通怪？ | 可以，確保爽感 |
| Boss 血量 | 普通怪 × 20-50 |
| 防禦減免上限 | 75% |
| 暴擊最大傷害 | ≤ 基礎傷害 × 3 |
| 每級屬性提升幅度 | 3-5% |

---

## LAYER 9：開源專案分析

### GDQuest RPG Demo（官方教學）
- **架構**：CharacterBody3D + StateMachine，Skill 系統 Node 掛載
- **Signal Bus**：EventBus.gd AutoLoad 解耦 UI 與邏輯
- **適合參考**：角色移動、攝影機系統、基礎狀態機

### SkeleRealms（社群 RPG 框架）
- **完整系統**：Inventory、Dialogue（Dialogic 2）、Quest、Save
- **存檔策略**：Resource.duplicate() + to_dict 序列化
- **值得學習**：SaveManager 的序列化策略

### Godot4-Tactical-RPG
- **Grid 系統**：TileMapLayer + AStarGrid2D 導航
- **Turn 管理**：Priority Queue（依 Speed 排序）
- **組合模式**：MovementComponent + AttackComponent
- **注意**：Godot 4 的 AStarGrid2D 和 3.x 差異很大

### 共同架構模式

```
AutoLoad Singletons
├── GameManager      全局遊戲狀態
├── EventBus         Signal 中繼站
├── SaveManager      存讀檔
├── ItemDatabase     物品資料查詢
└── QuestManager     任務狀態

角色節點組成
└── Character (CharacterBody2D/3D)
    ├── CharacterStats (Resource)
    ├── BuffManager (Node)
    ├── InventorySystem (Node)
    ├── MovementComponent (Node)
    ├── AttackComponent (Node)
    └── AnimationTree
```

---

## LAYER 10：踩坑表格

| # | 問題 | 解法 |
|---|------|------|
| 1 | **Resource 共享陷阱** | `resource.duplicate(true)` 深拷貝；Inspector 各自 Make Unique |
| 2 | **Signal 連接記憶體洩漏** | `CONNECT_ONE_SHOT` 或 `_exit_tree` 手動 disconnect |
| 3 | **StatModifier 浮點誤差** | `snapped(value, 0.01)` 或 `is_equal_approx` 比較 |
| 4 | **Inventory 排序破壞引用** | UI 用 `item.unique_id` 對應，而非 array index |
| 5 | **存檔包含 Node 引用** | 所有序列化改用純資料（String/int/float/Array/Dictionary）|
| 6 | **Buff 移除後屬性不歸零** | `remove_modifiers_from_source` source key 必須與 apply 時完全一致 |
| 7 | **QuestManager 事件洪水** | `call_deferred` 延遲；或批次蒐集一幀內事件 |
| 8 | **裝備詞綴加權重複抽** | weighted_sample 需從 remaining 移除已抽到的項目 |
| 9 | **ATB 暫停時仍在計時** | `if game_paused: return` 或 `set_process(false)` |
| 10 | **Dialogue 未觸發任務進度** | 對話結束需明確 emit 事件，不能假設自動偵測 |
| 11 | **GDScript 4.x 靜態類型陣列** | `Array[ItemStack]` 無法直接 assign `[]`，宣告時給類型 |
| 12 | **物理移動在 _process** | 所有物理移動必須在 `_physics_process` 內執行 |

---

## LAYER 11：EventBus + 存檔整合

```gdscript
# event_bus.gd (AutoLoad)
extends Node

signal quest_condition_met(condition_type: QuestData.ConditionType, target_id: String, amount: int)
signal enemy_killed(enemy_id: String, enemy_node: Node)
signal item_picked_up(item_id: String, quantity: int)
signal npc_talked(npc_id: String)
signal location_reached(location_id: String)
signal damage_dealt(target: Node, amount: float, is_critical: bool)
signal character_died(character: Node)
signal show_damage_number(position: Vector2, amount: float, is_critical: bool)
```

```gdscript
# 敵人死亡時的事件串聯
func die() -> void:
    EventBus.enemy_killed.emit(enemy_id, self)
    EventBus.quest_condition_met.emit(QuestData.ConditionType.KILL_ENEMY, enemy_id, 1)

# 裝備流程（完整）
var rare_sword = AffixGenerator.generate_item(sword_base, AffixGenerator.ItemRarity.RARE, player.level)
player.inventory.add_equipment_stack(rare_sword)
var old_item = player.equipment_slots.equip(rare_sword)
if old_item: player.inventory.add_equipment_stack(old_item)
```

---

## 認知框架

### 我能做的
- CharacterStats + StatModifier（加法/乘法/覆蓋三種，含快取與 dirty flag）
- Inventory（背包容量、裝備個體 unique_id、穿脫自動套用 modifier）
- QuestManager（條件追蹤、前置任務、獎勵發放、存讀檔序列化）
- Buff/Debuff（四種疊加策略，tick 傷害/治療）
- 裝備詞綴生成（加權隨機、tier 分級、品質等級）

### 誠實邊界
- 詞綴平衡數值需要實際遊戲測試調整
- 大量 Buff tick 的效能上限需實機測試

### 反模式（禁止）
- ❌ 直接修改共享 Resource：必須 `duplicate(true)`
- ❌ 存檔包含 Node 引用：只存純資料
- ❌ 物理移動在 `_process`：必須 `_physics_process`
- ❌ 每幀都重算所有 Stat：使用 dirty flag 快取
- ❌ Buff source key 不統一：集中常數管理

---

*版本：v2 | 最後更新：2026-04-19 | 適用：Godot 4.x GDScript*

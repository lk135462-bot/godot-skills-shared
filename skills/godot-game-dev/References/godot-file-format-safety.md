# Godot 資源檔安全（terma godot 吸收版）——LLM 手寫 .tscn/.tres 的守則

> 來源：bfollington/terma `plugins/tsal/skills/godot`（CC-BY-SA-4.0），2026-08-18 整合。
> 原文全文＋validator 腳本在 `vendor/terma-godot/`；本檔為情境適配摘要。

## 核心洞見

**`.gd` 是程式語言，`.tscn`/`.tres` 是嚴格序列化格式**——LLM 編輯 Godot 專案最高頻的失敗就是把 GDScript 語法寫進資源檔。

## 序列化格式鐵則

- 禁 `preload()`／`var`／`func` 出現在 .tscn/.tres
- 外部資源用 `ExtResource("id")`（檔頭需先宣告 `[ext_resource]`）；內嵌資源用 `SubResource("id")`
- 型別化陣列寫 `Array[Type]([...])`
- **實例化場景覆寫子節點屬性必須用 `index=` 語法**——忘了就是子組件拿到 null 靜默壞掉（Pitfall 5；`vendor/terma-godot/references/file-formats.md` 有 index 計算規則全文）

## 高頻 Pitfall 精選（全文十類在 `vendor/terma-godot/references/common-pitfalls.md`）

- `@onready`/`_ready()` 時序**由下而上**（子節點先於父節點 ready）：子節點內不可假設父節點已初始化；父節點在 `_ready` 可安全存取已 ready 的子節點
- `get_node()` 硬路徑改結構就斷——terma 原修法：groups／signals／find-by-type（godotprompter 另提供 export NodePath 法，見 vendor/godotprompter/godot-code-review.md §8）
- CPUParticles3D `color_ramp` 生效需 mesh material 開 `vertex_color_use_as_albedo`（出處：`vendor/terma-godot/SKILL.md` Pitfall 6——粒子類陷阱在 SKILL.md 主檔，common-pitfalls.md 無粒子條目）
- Godot 3→4 物理 API 改名重災區：`vendor/terma-godot/references/godot4-physics-api.md`（如 `PhysicsRayQueryParameters3D` 正確用法）

## 機械檢查（寫完資源檔必跑）

```
python vendor/terma-godot/scripts/validate_tscn.py <file.tscn>
python vendor/terma-godot/scripts/validate_tres.py <file.tres>
```
檢查面（兩支不同，別互相冒用）：
- `validate_tres.py`：preload 誤用／GDScript 關鍵字混入／未宣告 ExtResource／未型別化陣列——四項全抓
- `validate_tscn.py`：檔頭格式／未宣告 ExtResource＋SubResource／node 結構／parent 引用——**不抓** .tscn 內的 preload 與 GDScript 關鍵字（該類錯誤仍靠鐵則自律＋引擎載入驗證）

可掛 pre-commit。

## 適用場景定位

走**程式建構**路線的專案（UI／場景幾乎全在 GDScript 內 `new()` 組裝，手寫 `.tscn` 只剩一兩個殼）不會每天用到本檔；這套紀律真正的適用場景是：

1. **必須手寫／手改 `.tscn`/`.tres` 時**——改場景殼、做 `.tres` 資料檔
2. **派 LLM 代寫資源檔時**——工單附上本檔鐵則＋要求跑 validator，這是最高頻的失敗點
3. **三分離原則**（邏輯→`.gd`、資料→`.tres`、結構→`.tscn`）在「資料驅動內容」時參考：內容量小時用程式碼建 Resource 實例即可，等內容量大到需要非程式員編輯時再遷 `.tres`

架構模式範例（互動系統/屬性系統/資源化效果/背包/狀態機五套完整 GDScript）：`vendor/terma-godot/references/architecture-patterns.md`

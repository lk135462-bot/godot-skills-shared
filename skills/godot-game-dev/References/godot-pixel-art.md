# Godot 4 像素遊戲橫切面技術指南
# Pixel Art 呈現技術知識庫 v1

## 觸發條件
當專案是「像素美術（pixel art）呈現」的遊戲時使用——不論類型是 RPG、平台跳躍、Roguelike、塔防還是策略。本指南是**橫切面（cross-cutting）**：處理「像素怎麼正確畫到螢幕上」這一層（縮放、snap、TileMapLayer、攝影機抖動、2D 光影、匯入匯出），與七份類型指南**並用**，不取代它們。

---

## §0 版本座標與適用範圍

### 版本座標（2026-07 查證）

| 事實 | 版本 |
|---|---|
| 現行最新穩定版 | **Godot 4.7 stable（2026-06-18）**；4.6.3 為維護版 |
| integer scaling（`stretch/scale_mode="integer"`） | **4.2+**（PR #75784） |
| TileMapLayer（TileMap 同版起 deprecated）／Parallax2D／2D physics interpolation／`snap_2d_transforms_to_pixel` round 化（PR #87297） | **4.3+** |
| typed `Dictionary[K,V]`／2D batching 全後端／3D physics interpolation | **4.4+** |
| TileMapLayer physics chunk 合併（`physics_quadrant_size` 預設 16） | **4.5+** |
| Jolt 3D 物理預設（僅新專案，2D 不受影響）／tracing profiler | **4.6+** |
| 2D Scene Paint Mode（快捷鍵 B）／`one_way_collision_direction` | **4.7+** |

像素遊戲需要的三大底座（TileMapLayer、2D physics interpolation、round 版 pixel snap）**4.3 就齊了**；4.4 的 2D batching 與 4.5 的 physics chunking 是純效能紅利。新專案直接用 4.6.3 或 4.7，沒有理由停在舊版。

### 適用範圍

- 本指南管「像素呈現技術層」：§1–§3 開工設定、§4 TileMapLayer、§5 攝影機與手感、§6 光影、§7 shader、§9 匯出。
- 類型玩法系統（屬性、戰鬥、任務、波次…）→ 讀對應類型指南；§8 只放「像素遊戲特有」的手感速查與互鏈。
- `TileMap` 節點 4.3 起 deprecated——本指南所有範例一律用 **TileMapLayer**；視差一律用 **Parallax2D**。

---

## §1 開工首決策：三條縮放路線

**這是像素專案第一個、也是最不可逆的決策。** 縮放路線決定光影解析度（§6）、粒子與 tween 的呈現方式、攝影機架構（§5）、UI 佈局（§2）——事後換路線等於把特效、相機、UI 全部重做。開工第一天就選定，寫進專案 README。

### 三條路線

| 路線 | 組合 | 本質 | 適合 |
|---|---|---|---|
| **A：純復古** | `stretch/mode="viewport"` + `aspect="keep"` + `scale_mode="integer"` | 整個畫面（含 UI、粒子、光影）固定以低解析度渲染再整數放大，一切鎖在同一像素格 | GB／NES 式嚴格 pixel-perfect；截圖會被放大檢視的遊戲 |
| **B：像素美術＋平滑** | `stretch/mode="canvas_items"` + `scale_mode="integer"` + Nearest filter + `snap_2d_transforms_to_pixel=true` | 以視窗全解析度渲染，sprite 仍銳利，但相機、粒子、tween 有真正的 sub-pixel 平滑（Celeste／Hyper Light Drifter 路線） | 要平滑相機、高解析粒子、旋轉物件的現代像素遊戲 |
| **C：低解析遊戲＋高解析 UI** | `SubViewportContainer > SubViewport`（低解析畫面）＋外層 CanvasLayer（高解析 UI）＋可選雙相機平滑 | 遊戲世界鎖低解析，UI／字體／過場用全解析度 | 文字量大（RPG 對話、策略面板）又想保留復古畫面的遊戲 |

### 決策表

| 你的需求 | 選 |
|---|---|
| 一切都要在同一像素格上、UI 也是像素字 | A |
| 相機要平滑跟隨、粒子要細膩、有旋轉元素 | B |
| 低解析畫面＋清晰的高解析 UI／中文字體 | C |
| 想省事、第一款像素遊戲 | B（開發成本低一個數量級） |
| 光暈與影子也要「像素顆粒感」 | A 或 C（光影以 viewport 解析度計算，見 §6） |

判斷心法：把每個「連續量」（相機位置、粒子軌跡、縮放動畫）都問一次「snap 到像素格之後還成立嗎」——大量依賴平滑連續量的設計選 B／C，否則 A 最純。

> ⚠️ **不可逆警告**：路線 A 換 B 意味著光影從顆粒變平滑、粒子參數全部重調；B 換 A 意味著平滑相機架構整組作廢、UI 字體要換 bitmap font。**不要兩邊混搭到一半。**

---

## §2 可直接抄的 project.godot 設定包

### 路線 A：純復古（viewport + keep + integer）

```ini
[display]

window/size/viewport_width=640
window/size/viewport_height=360
; 開發時的視窗大小（不影響遊戲邏輯解析度）
window/size/window_width_override=1920
window/size/window_height_override=1080
window/stretch/mode="viewport"        ; 整個 viewport 低解析渲染再放大
window/stretch/aspect="keep"          ; 鎖比例；expand+integer 組合有已知邊角問題，keep 最穩
window/stretch/scale="1.0"
window/stretch/scale_mode="integer"   ; 4.2+；整數倍縮放杜絕不均勻像素

[rendering]

textures/canvas_textures/default_texture_filter=0   ; 0 = Nearest
2d/snap/snap_2d_transforms_to_pixel=true            ; 4.3 起為 round 版，穩定
2d/snap/snap_2d_vertices_to_pixel=false             ; 保持 false；只有旋轉/縮放仍 shimmer 才加開

[physics]

common/physics_interpolation=true     ; 4.3+ 2D physics interpolation 總開關
```

### 路線 B：像素美術＋平滑相機（canvas_items + integer + snap）

```ini
[display]

window/size/viewport_width=640
window/size/viewport_height=360
window/size/window_width_override=1920
window/size/window_height_override=1080
window/stretch/mode="canvas_items"    ; 高解析渲染、sprite 仍銳利
window/stretch/aspect="keep"
window/stretch/scale="1.0"
window/stretch/scale_mode="integer"   ; 4.2+

[rendering]

textures/canvas_textures/default_texture_filter=0   ; 0 = Nearest
2d/snap/snap_2d_transforms_to_pixel=true            ; 渲染端最後一步取整，與 interpolation 相容
2d/snap/snap_2d_vertices_to_pixel=false

[physics]

common/physics_interpolation=true     ; 4.3+
```

兩份共通要點：

- snap 發生在**渲染階段**，邏輯座標保持連續，因此與 2D physics interpolation 相容——像素遊戲通常「插值＋snap」一起開反而穩，但需實測。
- `aspect="keep_height"` 適合橫向捲軸（鎖高度、寬螢幕看更多）；`expand` 支援 21:9 等多比例，但與 `integer` 併用在特定視窗尺寸有已知非預期行為（issue #92055、#108155），求穩用 `keep`。

### 畫布解析度對照

| 解析度 | 到 1080p | 到 1440p | 到 4K | 備註 |
|---|---|---|---|---|
| **320×180** | 6x 整數 | 8x 整數 | 12x 整數 | 最復古；三大主流解析度全整數，最安全 |
| **640×360** | 3x 整數 | 4x 整數 | 6x 整數 | **官方推薦值**；資訊量與像素感最平衡 |
| **480×270** | 4x 整數 | ~5.33x ✗ | 8x 整數 | **1440p 陷阱**：非整數，integer 模式會降到 5x 留大黑邊——除非明確放棄 1440p 使用者，否則避開 |

選法：①16:9 為基準；②能整除 1920×1080／2560×1440／3840×2160 者優先；③以角色尺寸反推（先定角色像素高，再選能容納目標視野的解析度）。預設 **640×360**，更粗獷復古選 **320×180**。

### 路線 C：SubViewport 架構與三大陷阱

標準場景結構：

```text
Root
├── SubViewportContainer          # Full Rect anchors
│   └── SubViewport               # size = 畫布解析度、render_target_update_mode = Always、disable_3d = true
│       └── LowResGame
│           ├── LowResCamera (Camera2D)   # 硬跟隨、global_position.round()
│           ├── Player (CharacterBody2D)
│           └── TileMapLayer
├── HighResCamera (Camera2D)      # 可選：負責平滑（zoom = 放大倍率）
└── UI (CanvasLayer)              # 高解析 HUD，完全不受低解析限制
```

**三大陷阱（每個 SubViewport 都要檢查）**：

1. **不吃專案 filter 預設**：引擎只對 root viewport 套用 `default_texture_filter`，SubViewport 維持類別預設 Linear——「為什麼 SubViewport 裡還是糊的」九成是這個。必須自設：
   ```gdscript
   $SubViewport.canvas_item_default_texture_filter = \
       Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
   ```
2. **snap 是 per-viewport 屬性**：`Viewport.snap_2d_transforms_to_pixel` 預設 `false`，專案設定只影響主視窗；SubViewport 需要 snap 要自己開。
3. **粒子抖動（issue #98764）**：SubViewport 內開 snap、粒子節點以非整數移動且 `local_coords` 關閉時，移動中的 GPUParticles2D 會抖——粒子節點盡量不要跟著移動物件走，或設 `local_coords = false` 讓已發射粒子留在世界空間。

---

## §3 素材匯入（Texture Import）

| 設定 | 值 | 理由 |
|---|---|---|
| Compress → Mode | **Lossless**（2D 預設） | 官方文件明言 Lossless 是 pixel art 的推薦設定；顯示結果與原圖 byte-perfect |
| Mipmaps → Generate | **Off**（2D 預設） | 像素風不需要縮小模糊圖，開了多吃約 33% 記憶體 |
| VRAM Compressed | **不要用** | 塊狀壓縮（4×4 block）把相鄰像素平均化，對 2D 有明顯 artifacts，低解析度貼圖尤甚——直接毀掉單像素細節 |

**Godot 4 的 filter 誤區**：與 Godot 3 不同，**filter 不在 import 設定裡**。設定位置有三層：

1. 全專案預設：`rendering/textures/canvas_textures/default_texture_filter = Nearest`（像素遊戲一律先改這個）。
2. per-Viewport：`Viewport.canvas_item_default_texture_filter`（SubViewport 必設，見 §2）。
3. per-node：`CanvasItem.texture_filter`，預設 `TEXTURE_FILTER_PARENT_NODE` 沿父節點繼承；混合美術風格時對個別節點覆寫（如高解析 logo 設回 Linear）。

其他要點：

- **atlas 防滲色**：sprite sheet 相鄰 frame 之間留 1–2px padding（或匯入時設 margin），否則縮放取樣時鄰格顏色會滲進來；outline shader 一類會取樣邊緣的效果也需要 sprite 四周留透明邊距。
- **批次套用**：FileSystem 多選檔案（或整個資料夾）→ Import dock 改設定 → Reimport；或 Import dock → Preset → Set as Default for 'Texture' 設專案預設。
- **音訊才是 PCK 大頭**：像素貼圖極小，BGM 用 OGG Vorbis（96–128 kbps 夠用），別放 WAV 長音樂。

---

## §4 TileMapLayer 工作流

### 4.1 一層一節點（4.3+）與遷移

- 4.3 起官方作法是**每層一個 `TileMapLayer` 節點**、多層共用同一個 TileSet resource；樹中順序即繪製順序。每層有獨立的 `collision_enabled`／`navigation_enabled`／`occlusion_enabled` 開關與標準 CanvasItem material（可各層掛 shader）。
- **一鍵遷移**：選舊 TileMap 節點 → 底部 TileMap 面板 → 右上工具箱 → 「Extract TileMap layers as individual TileMapLayer nodes」。
- 遷移陷阱：轉換器只對可直接打開的場景有效（tile 資料在 `.tres` 或 instanced scene 裡要手動搬）；遷移後常見 collision 消失（physics layer bitmask 被重設）與 terrain 角落畫錯（peering bits 缺漏）——**遷移後立刻開 Debug → Visible Collision Shapes 跑一次遊戲驗證**。
- 座標限制：cell 座標為 16-bit signed（-32768～32767）。

### 4.2 Terrain sets（autotiling）

- 三種 matching mode：`Match Corners and Sides`（3×3）／`Match Corners`（2×2）／`Match Sides`。核心是 Peering Bits：3×3 格描述各方向鄰居應為何種 terrain，`-1` 代表空格。
- **沒有自動偵測**：切完 atlas 後 terrain 資料全空，必須逐 tile 設 peering bits；大量 tile 用 TileSet editor 的 **Paint 模式**加速（collision、custom data 也能刷）。48-tile blob 建議採社群通用模板圖排列，設一次後把 TileSet 存成獨立 `.tres` 重用。
- **內建演算法缺陷**：Godot 4 內建 terrain 在某些 peering bits 組合下選錯 tile 的比率偏高（godot-proposals #7670，2026 年仍未解）。判斷準則：**只在編輯器畫地圖 → 內建夠用；執行期改地形（挖掘、農場、蓋房）→ 直接上 Better Terrain 外掛**（§10），不要跟內建演算法搏鬥。

### 4.3 Y-sort 標準場景樹模板

```text
World (Node2D, y_sort_enabled = ON)
├── Ground      (TileMapLayer, y_sort_enabled = OFF)   # 純地板，永遠在最下面
├── GroundDecal (TileMapLayer, y_sort_enabled = OFF)
├── Props       (TileMapLayer, y_sort_enabled = ON)    # 樹、牆、家具等會遮擋物
│     └─ 逐 tile 設 Y Sort Origin ≈ tile 圖像「腳底」相對 tile 原點的 y 偏移
├── Player      (CharacterBody2D)                      # sprite 原點對齊腳底
└── NPCs / 互動物件
```

鐵則：

- **角色 sprite 原點必須在腳底**：Y-sort 用節點 `position.y` 排序，把 Sprite2D 的 `offset.y` 設為負的（圖高－腳底距離），讓節點 position 即腳底。
- 角色與 TileMapLayer 必須是**同一個 y_sort_enabled 父節點的兄弟節點**，否則排序不生效。
- **多格高物件（2 格高的樹、牆）是 Y-sort 最大痛點**，引擎內沒有一勞永逸的乾淨解。可行解法：①垂直切到多個 TileMapLayer（「腳層」「身體層」各設不同 `y_sort_origin`）；②整個物件併成一張大 atlas tile 由 tile 自己的 origin 排序；③**最穩：做成獨立 Sprite2D scene（origin 在腳底）而非 tile**。
- 已知 bug：scene tiles 會忽略該層的 `y_sort_origin`（issue #89927），scene tile 需要排序時在 scene 內自己控制。
- 效能 trade-off：y-sorted layer 的 rendering quadrant 批次失效（改按 Y 分組），draw call 較多——純地板層一律 y_sort OFF。

### 4.4 Physics / Navigation / Occlusion 配置

- 三者都在 **TileSet resource** 上 Add Element 建層、逐 tile 畫 polygon：physics 按 **F** 產生整格矩形再編輯；navigation 畫尋路 polygon；occlusion 供 2D 光影（LightOccluder）用。
- 慣用分層：physics layer 0 = 地形阻擋（牆／水），layer 1 = 僅特定單位阻擋（矮柵欄）。
- **navmesh 不可疊層**（官方警告）：多個 TileMapLayer 各自產生的 navigation mesh 疊在同一 map 上會 merge 出錯——navigation 只放在**一個** ground 層的 TileSet 上，其他層 `navigation_enabled = false`；更好的尋路走 NavigationRegion2D 烘焙或 NavigationServer2D。
- Custom Data Layers 順手建一個（如 `terrain_type`），腳步聲／速度修正直接 `get_cell_tile_data(coords).get_custom_data("terrain_type")` 讀。

### 4.5 程序生成範式

```gdscript
# 正範式：先收集整批 cells，最後一次 set_cells_terrain_connect
@onready var ground: TileMapLayer = $World/Ground

func generate(width: int, height: int) -> void:
    var grass_cells: Array[Vector2i] = []
    var noise := FastNoiseLite.new()
    noise.seed = randi()
    for x: int in width:
        for y: int in height:
            if noise.get_noise_2d(float(x), float(y)) > 0.0:
                grass_cells.append(Vector2i(x, y))
    # terrain_set = 0, terrain = 0；一次整批
    ground.set_cells_terrain_connect(grass_cells, 0, 0)

# 非 terrain 的直接放置（source_id 0、atlas 座標 (1, 2)）
func place_tile(coords: Vector2i) -> void:
    ground.set_cell(coords, 0, Vector2i(1, 2))

# 挖掉一格 = 放空 tile
func dig(coords: Vector2i) -> void:
    ground.set_cell(coords, -1)
```

- ❌ **反模式：逐格呼叫 `set_cells_terrain_connect`**——逐格呼叫會彼此覆蓋出錯，必須一次傳入整批 cells（社群大量踩雷實錄）。
- `update_internals()` 時機：set_cell 後的內部更新（含 physics／navigation 重建）預設**批次延後到幀尾**；只有「同一幀內就要碰撞生效」才呼叫 `update_internals()`（官方警告：昂貴）。`notify_runtime_tile_data_update()` 是給 `_tile_data_runtime_update()` 機制用的，**不是** set_cell 後同步 physics 的手段。

### 4.6 效能：quadrant 對照表與大地圖策略

`rendering_quadrant_size`（預設 16）把 N×N 格合併為單一 CanvasItem 減 draw call；`physics_quadrant_size`（**4.5+**，預設 16）控制 collision chunk 合併大小。4.5 的 chunk 合併是破壞相容的：`get_coords_for_body_rid()` 一個 body 可能涵蓋多格。

| 場景 | rendering_quadrant_size | physics_quadrant_size |
|---|---|---|
| 一般固定關卡 | 16（預設） | 16（預設） |
| 大型戶外靜態地圖 | 32～64 | 16 |
| 頻繁挖/放 tile（挖掘、農場） | 16 | 4～8（重建範圍小） |
| 需要精確知道「碰到哪一格」 | 16 | **1** |
| 常整層開關可見性的小區域 | 4 | 16 |

大地圖策略：

- 編輯器單層約 500×500 格後變卡（筆刷預覽每幀重算）；切成多個 250×250 的 layer 可保編輯流暢。執行期 2000×2000 tile 仍可高幀率。
- 開放世界：每 chunk 一個 TileMapLayer（64×64～256×256 格）掛在 chunk manager 下，玩家半徑外 `enabled = false` 或整個 free；生成用 thread ＋ `call_deferred` 掛回樹。
- 純視覺遠景層把 collision／navigation／occlusion 三開關全關，省物理與 navmesh 建置。
- 「TileMap 碰撞會爆 body 數」這個老常識 **4.5+ 已不成立**（chunk 合併）——看到這類效能建議先對版本。

---

## §5 攝影機與抖動（jitter）

### 5.1 jitter 五類成因

| 成因 | 機制 |
|---|---|
| 次像素 transform | 相機/物件落在小數位置，GPU 在 texel 間取樣 → shimmer/wobble |
| 非整數縮放倍率 | fractional scale 下像素寬度不一 → 移動時像素「爬行」 |
| physics 與 render 頻率不同步 | 物理 60 tick、螢幕 144/165Hz → 微觀 stutter |
| 相機與角色在不同 callback 更新 | 一個在 `_physics_process`、一個在 `_process` → 每幀差一小段 |
| snap ＋ camera smoothing 併用 | 平滑值是小數，snap 把相機與角色各自往不同方向取整 → 互相追逐的抖動 |

官方坦承這是痛點（proposal #6389 closed as not planned）：引擎沒有內建 PixelCamera2D，「完美像素＋完美平滑相機」必須自己組。

### 5.2 除錯 SOP（固定順序，逐步排除）

1. **integer scaling**：確認 `scale_mode="integer"`——先排除縮放性抖動。
2. **snap transforms**：開 `snap_2d_transforms_to_pixel=true`（4.3+ 才建議放心開）。
3. **統一時序**：相機與角色**同在 `_physics_process` 更新**；Camera2D 的 `process_callback = CAMERA2D_PROCESS_PHYSICS`。
4. **關 position smoothing**：`position_smoothing_enabled = false`。
5. **開 2D physics interpolation**：`physics/common/physics_interpolation=true`（4.3+），消高刷新率螢幕上的物理性 stutter。
6. 走完 1–5 仍要平滑相機 → 上 SubViewport 雙相機或子像素偏移架構（下述）。

> **鐵則：`snap_2d_transforms_to_pixel` 與 Camera2D 內建 position smoothing 不可併用。** 要平滑就走架構解，不是把兩個互打的開關同時打開。

### 5.3 路線 B（viewport）的平滑相機：snap ＋ 殘差回饋

原理：相機邏輯位置用 float 平滑追蹤 → render 位置 `round()` 給低解析 viewport → 把「float − round 後」的 sub-pixel 殘差乘上放大倍數，位移最終放大後的呈現層。SubViewport 尺寸比目標多留 1–2px 邊避免露黑邊。

```gdscript
extends Camera2D
## 平滑像素攝影機：內部 float 追蹤，render 前 snap，殘差交給放大層。
@export var target: Node2D
@export var smooth_speed: float = 8.0
@export var scale_factor: int = 4          # 視窗放大倍數（integer scale）
var _float_pos := Vector2.ZERO

func _physics_process(delta: float) -> void:
    # 1) float 平滑（frame-rate independent lerp）
    _float_pos = _float_pos.lerp(target.global_position,
        1.0 - exp(-smooth_speed * delta))
    # 2) snap 到整像素給低解析 viewport
    global_position = _float_pos.round()
    # 3) 殘差 × 放大倍數 → 位移最終呈現層
    var frac := _float_pos - global_position   # ∈ (-0.5, 0.5)
    %GameViewport.position = -frac * float(scale_factor)
```

### 5.4 Trauma-based screen shake

原理（GDC「Juicing Your Cameras With Math」，跨引擎公認做法）：維護 `trauma ∈ [0,1]`，事件**加** trauma、隨時間線性衰減；實際 shake 量 = `trauma²`（非線性讓小創傷幾乎無感、大創傷猛烈）；位移用連續雜訊（FastNoiseLite）採樣而非純亂數，平移與旋轉各用獨立雜訊軸。

```gdscript
extends Camera2D
## Trauma-based screen shake（掛在主 Camera2D，autoload 轉呼叫亦可）
@export var decay: float = 0.8                    # trauma 每秒衰減量
@export var max_offset := Vector2(6, 4)           # 低解析座標下的最大位移
@export var max_roll: float = 0.0                 # 像素遊戲建議 0（旋轉破壞像素網格）
@export var trauma_power: float = 2.0

var trauma := 0.0
var _noise := FastNoiseLite.new()
var _t := 0.0

func _ready() -> void:
    _noise.seed = randi()
    _noise.frequency = 0.5

func add_trauma(amount: float) -> void:
    trauma = clampf(trauma + amount, 0.0, 1.0)

func _process(delta: float) -> void:
    if trauma <= 0.0:
        offset = Vector2.ZERO
        return
    trauma = maxf(trauma - decay * delta, 0.0)
    _t += delta * 60.0
    var amt := pow(trauma, trauma_power)
    rotation = max_roll * amt * _noise.get_noise_2d(0.0, _t)
    offset = Vector2(
        max_offset.x * amt * _noise.get_noise_2d(100.0, _t),
        max_offset.y * amt * _noise.get_noise_2d(200.0, _t),
    ).round()   # 像素遊戲：offset 要 round()，路線 B 尤其必要
```

呼叫慣例：小受擊 `add_trauma(0.3)`、中爆炸 `add_trauma(0.5)`、Boss 落地 `add_trauma(0.8)`。像素遊戲三注意：①offset 要 `round()` 且 max_offset 用小值（4～8px，低解析下 2px 已很有感）；②`max_roll` 設 0（旋轉整個低解析畫面產生鋸齒混疊）；③**提供關閉/減弱 shake 的無障礙全域倍率開關**（暈眩玩家，業界慣例）。

### 5.5 Hitstop / Freeze Frame

```gdscript
# autoload：GameFeel.gd
var _freezing := false

func hitstop(duration: float = 0.08, scale: float = 0.05) -> void:
    if _freezing:
        return                          # 防重入：連續命中不疊加
    _freezing = true
    Engine.time_scale = scale
    # 關鍵：create_timer 第四參數 ignore_time_scale = true，
    # 否則 timer 也被減速，凍結時間被放大 1/scale 倍
    await get_tree().create_timer(duration, true, false, true).timeout
    Engine.time_scale = 1.0
    _freezing = false
```

- `time_scale = 0.05`（極慢動作）比 `= 0` 安全：物理不完全停擺、await/tween 不卡死。
- `Engine.time_scale` 是全域的；需要豁免的 Tween 用 `tween.set_ignore_time_scale(true)`。
- 參數速查：普通命中 0.03～0.05s／重擊 0.08～0.12s／擊殺 0.15～0.25s。常與 shake 綁成一個呼叫（命中先凍結、解凍瞬間 shake 開始）。

---

## §6 2D 光影

### 6.1 第一原則：光影以 Viewport 解析度計算

官方文件明寫：2D lighting 與 shadow 以 **Viewport 的像素解析度**計算，不是貼圖 texel——就算 sprite 全 Nearest，光暈和影邊在高解析 viewport 下仍是平滑漸層。**要「像素顆粒感的光」，正解是走低解析 viewport（路線 A 或 C）**；路線 B（canvas_items）下光影天生是高解析平滑的，接受它或用 banded light shader 補味（§7）。低解析 viewport 同時是最大的效能紅利——光影計算量隨 viewport 像素數線性成長。

### 6.2 每 CanvasItem 16 燈硬上限

每個 CanvasItem 最多被 **16 盞燈**影響（硬編碼），超過出現明顯 artifact。Workaround：縮小受光 sprite、調小 TileMap quadrant（讓每個合併後的 CanvasItem 更小）、或幾十盞燈的洞穴／視野需求改「軟體打光」（自己維護亮度網格寫進 modulate 或低解析亮度貼圖給 shader 取樣——Terraria 路線）。

### 6.3 真光≤5 盞，其餘假光

- 燈越大張（`texture_scale` 越大）影響的 pixel 越多越貴。**真 Light2D（要投影／normal map 的）只留 3～5 盞主光**；火堆、螢火蟲、彈道光等大量小光點用 **Add-blend 的 Sprite2D 假光**（CanvasItemMaterial `blend_mode = Add`），官方文件「Performance Alternatives」明載此法便宜得多。
- PointLight2D 光形貼圖不必進繪圖軟體：`GradientTexture2D` + Fill=Radial 即生放射光斑；**Gradient 插值設 Constant 畫成同心圓色帶**，是零 shader 的「像素風光暈」最便宜解。

### 6.4 陰影與 occluder

- `shadow/enabled` 開了不會馬上有影子——**場上必須有 LightOccluder2D**（官方明講的新手陷阱）；tile 用 TileSet 內建 occlusion 層（§4.4）比手放 LightOccluder2D 好管理，多邊形頂點數壓最低（方塊 tile 4 頂點）。
- **自遮擋**：sprite 自己的 occluder 會把自己壓黑。解法：OccluderPolygon2D 的 `cull_mode` 設 **CounterClockwise**（影子只向外投）；或用 `occluder_light_mask` × 燈的 `shadow/item_cull_mask` 排除自己。角色一般不給 occluder（避免自遮擋與滿地雜影）。
- **DirectionalLight2D 的影子永遠無限長**，不受 `height` 影響——官方明載的限制；夕陽長影可以，「短影正午」做不出來。
- **shadow filter 一律 `None`**：PCF 軟影與像素風衝突，`None` 最快也最貼風格；`shadow_color` alpha 約 0.6–0.8 做半透明影。
- **GL Compatibility 後端的 PointLight2D 貼圖可能發糊**（非 pixel-perfect 對齊時，issue #90360）；Forward+／Mobile 正常，低階裝置目標要實測。

### 6.5 Normal map（TileSet 與 sprite）

- 引擎側：貼圖換成 **`CanvasTexture`**（diffuse＋normal＋specular 三合一資源）——TileSet 的 tile source 貼圖同樣走 CanvasTexture 即可吃 normal map（Godot 4 現況正解）。掛 normal 後畫面會變暗，用燈的 `height` 與 `energy` 補償。
- 工具：**Laigter**（免費開源、活躍維護）拖圖自動生 normal/parallax/specular/occlusion，可即時預覽打光——像素 sprite 批產首選（§10）。
- 心法：低解析像素圖自動生成的 normal 容易「塑膠感」；<32px 小角色通常不值得上 normal，效果留給大型場景件（牆、石柱、Boss）。normal map 也保持 Nearest filter。

### 6.6 日夜循環與 UI 隔離

```gdscript
# 場景根掛 CanvasModulate，Gradient 驅動全畫布色調
@export var day_gradient: Gradient   # 0.0=午夜深藍 → 0.25=晨橘 → 0.5=正午白 → 0.75=暮紅 → 1.0=午夜
@export var day_length_sec: float = 600.0
@onready var canvas_mod: CanvasModulate = $CanvasModulate

var time_of_day := 0.5   # 0..1

func _process(delta: float) -> void:
    time_of_day = fmod(time_of_day + delta / day_length_sec, 1.0)
    canvas_mod.color = day_gradient.sample(time_of_day)
```

- 經典夜景配方：CanvasModulate 壓到約 `(0.12, 0.15, 0.3)`＋火把 PointLight2D（blend=Add、暖色、filter=None）。
- **UI 放獨立 CanvasLayer**——CanvasModulate 只影響同一 canvas，UI 才不會跟著被壓暗。
- 點光源（路燈、窗光）訂閱時鐘的整點 signal 開關（§8.6），日夜視覺與時間邏輯分兩層、單向驅動。

---

## §7 像素 shader 配方索引

配方細節與現成實作**路由到 `godot-shader-developer` agent 與 godotshaders.com**，這裡只放「掛法」與「選用準則」。全部 `shader_type canvas_item`、Godot 4 語法（`source_color`、`hint_screen_texture`；3.x 的 `hint_color`／`SCREEN_TEXTURE` 已棄用）。

| 配方 | 用途 | 選用準則 |
|---|---|---|
| **Hit flash（受擊閃白）** | mix(tex.rgb, flash_color, strength)，GDScript 用 Tween 打 uniform | 任何有戰鬥的像素遊戲標配；多實例注意 `material.resource_local_to_scene = true` 或用 per-instance uniform（4.3+ canvas_item 支援） |
| **Palette swap（調色盤置換）** | 來源色→目標色陣列比對置換 | 換裝／敵人變體用 per-sprite 版；GB 四色全螢幕風格用 CanvasLayer＋ColorRect 掛 LUT 版 |
| **Banded / quantized light（色帶化打光）** | 覆寫 `light()`，把平滑光衰減 `floor(atten * bands) / bands` 量化成階梯 | 路線 B 想要「像素感的光」但不想上 SubViewport 時的補味手段；零 shader 替代：光形貼圖直接畫成同心圓色帶（§6.3） |
| **Bayer dither（抖點漸層）** | 4×4 Bayer 矩陣把亮度量化成兩色抖點 | 陰影漸層、霧、漸暗轉場的復古化；FRAGCOORD 除以 pixel_scale 對齊放大倍率 |
| **CRT / scanline 後製** | 桶狀變形＋掃描線＋暗角 | 見下方掛法；`scanline_count` 對齊 base viewport 高度 |

**全螢幕後製的標準掛法**：`CanvasLayer > ColorRect`（Full Rect、`mouse_filter = Ignore`），shader 放 ColorRect，讀螢幕用：

```glsl
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
```

**UI 後製注意**：Godot 4 的 UI 上後製 shader 有 backbuffer 讀取順序問題——要讓後製蓋到 UI（或刻意不蓋），用 **`BackBufferCopy`** 節點或 CanvasLayer 分層控制順序，不要硬堆節點順序碰運氣。

---

## §8 類型手感速查（與類型指南互鏈，不重複展開）

### 8.1 Platformer 八常數表

完整角色物理與關卡設計 → `References/godot-platformer.md`。像素平台跳躍的社群公認起手值：

```gdscript
const COYOTE_TIME := 0.10           # 離開平台後仍可跳的秒數
const JUMP_BUFFER := 0.10           # 落地前按跳仍算數的秒數
const JUMP_CUT := 0.45              # 提早放開跳躍鍵時保留的上升速度比例
const RISE_GRAVITY_MULT := 0.9      # 上升期重力（略飄）
const FALL_GRAVITY_MULT := 1.5      # 下落期重力（下落快於上升＝單一最有感的手感改動）
const APEX_SPEED_THRESHOLD := 45.0  # |velocity.y| 低於此值視為頂點附近
const APEX_GRAVITY_MULT := 0.55     # 頂點附近超輕重力（hang time）
const MAX_FALL_SPEED := 400.0       # 終端速度
```

buffer 與 coyote 兩計時器同時有效才跳；jump cut =「放開跳躍鍵且仍上升時 `velocity.y *= JUMP_CUT`」。參數化心法：用「跳 3 格高、0.35 秒到頂」反推（`g = 2h/t²`、`v0 = -2h/t`）比直接調 gravity 更好溝通。

### 8.2 Top-down 移動：grid-based vs free movement

| 判準 | 選 grid-based | 選 free movement |
|---|---|---|
| 玩法核心 | 解謎、回合制、Pokemon／倉庫番類 | 動作戰鬥、Zelda／Stardew 類 |
| 碰撞 | RayCast 一格一查（`force_raycast_update()`），極簡 | CharacterBody2D + move_and_slide |
| 動畫 | 4 方向足矣 | 4 或 8 方向＋BlendSpace2D |

有即時戰鬥一律 free movement。grid 版三要點：`force_raycast_update()` 不等物理幀、`moving` 旗標鎖輸入、Tween 補間格子移動。

### 8.3 方向動畫：4 方向＋flip_h 省半美術

- 純 4 方向像素風的通行做法：**只畫 4 方向動畫、左右共用一組 `flip_h`**，美術量省一半。
- AnimationTree 用 **BlendSpace2D**（X/Y 軸放移動向量、`blend_position` 餵 input 向量），Idle 與 Walk 各一個、StateMachine 切換，停下時保留最後方向（只在 input 非零時更新 blend_position）。
- **BlendSpace2D 的 blend mode 設 `Discrete`**——像素動畫不要插值混合，會出現半透明疊影。

### 8.4 Hitbox / Hurtbox（GDQuest 架構）

Hitbox＝造成傷害（掛武器／攻擊動畫）；Hurtbox＝接受傷害（掛角色）。單向偵測配置：

| | collision_layer | collision_mask | monitoring |
|---|---|---|---|
| HitArea2D（hitbox） | 2（hitbox 層） | 0 | off |
| HurtArea2D（hurtbox） | 0 | 2（只聽 hitbox 層） | on |

- hitbox 的 CollisionShape2D 平時 `disabled = true`，由 **AnimationPlayer 攻擊動畫的關鍵幀開關**——判定跟動畫幀走，不跟計時器走。
- 物理回呼中改碰撞狀態用 `set_deferred("disabled", ...)`。
- **無敵幀直接 `set_deferred("monitoring", false)`** 比留 flag 保險（連 `area_entered` 都不發，避免同一 hitbox 停留期間重複觸發）：

```gdscript
# Hurtbox.gd
signal damaged(amount: int, source: Node2D)

func start_invincibility(duration: float = 0.8) -> void:
    set_deferred("monitoring", false)
    await get_tree().create_timer(duration).timeout
    set_deferred("monitoring", true)
```

持續接觸型傷害（站岩漿）用 `get_overlapping_areas()` ＋ tick timer，別依賴只發一次的 `area_entered`。起手骨架可直接 clone gdquest-demos/godot-4-hitbox-hurtbox。

### 8.5 互動系統：主動／被動雙 Area2D

- **被動件**掛可互動物件（NPC、告示牌、寶箱），定義三個 signal：`interacted`、`interaction_available`、`interaction_unavailable`；**主動件**掛玩家、負責 overlap 偵測。兩者放**專屬 physics layer**，與地形／戰鬥層隔離。
- 多候選時選最近目標（`distance_squared_to` 比距離省開根號）；提示 UI（頭上「按 E」）接 available/unavailable 兩個 signal 開關。
- top-down 把玩家的 InteractionArea 做成**面向前方的偏移小圓**（隨面向轉），比全身大圓更直覺；platformer 用全身範圍即可。

### 8.6 NPC 排程：Resource 資料＋整點 signal＋state machine

- 排程資料用 **Resource**（type safety＋Inspector 可編輯），與 NPC 邏輯分離；時間用 autoload 時鐘廣播**整點 signal**，NPC 訂閱事件、不要每幀查時間；「按表操課＋對玩家反應」由 state machine 執行，排程只是餵狀態機目標的資料層。

```gdscript
# game_clock.gd — autoload
signal hour_changed(day: int, hour: int)

var seconds_per_game_hour: float = 42.0
var day := 1
var hour := 6
var _acc := 0.0

func _process(delta: float) -> void:
    _acc += delta
    if _acc >= seconds_per_game_hour:
        _acc = 0.0
        hour = (hour + 1) % 24
        if hour == 0:
            day += 1
        hour_changed.emit(day, hour)
```

```gdscript
# schedule_entry.gd
class_name ScheduleEntry
extends Resource

@export var hour: int = 8
@export var target_marker: String = "Home"   # 場景中 Marker2D 名
@export var activity: String = "idle"        # 抵達後餵給狀態機的狀態
```

移動用 NavigationAgent2D ＋ Marker2D 錨點；跨場景 NPC 只更新「邏輯位置」、玩家進場景才實體化（Stardew 式通行簡化）。RPG 完整任務／對話系統 → `References/godot-rpg-game.md`；策略遊戲時間系統 → `References/godot-strategy-game.md`。

---

## §9 匯出（Web 與桌面）

### 9.1 Web

- Godot 4 web export = WebAssembly + WebGL 2.0（僅 Compatibility renderer）；Safari 相容性較差，官方建議 Chromium/Firefox。
- **4.3+ single-threaded 匯出是預設且官方偏好**：不需要 SharedArrayBuffer，因此**不需要 COOP/COEP header**，itch.io／Poki／CrazyGames 直接相容。只有勾 Thread Support 才要求 `Cross-Origin-Opener-Policy: same-origin` ＋ `Cross-Origin-Embedder-Policy: require-corp` ＋ HTTPS。
- **像素遊戲幾乎總是選 single-threaded**：CPU/GPU 負擔輕，效能損失無感，換到最好的平台相容性。
- 音訊：預設「Sample」模式**不支援 AudioEffect／reverb**（web 上靜默失效）——只用檔案播放 SFX/BGM；首次互動後才播 BGM（瀏覽器 autoplay 政策）。
- **C# 專案目前不能匯出 web**（官方文件明載）；要 web 就用 GDScript。
- `.wasm` 要以 `application/wasm` MIME type 供應；伺服器 gzip/brotli 後 **wasm 約可壓到原大小 1/4**（GitHub Pages 自動 gzip；itch.io 需自行預壓縮）。
- wasm64：4.7 只完成建置層，**匯出流程尚未支援，不要當可用功能規劃**。

### 9.2 桌面

- 全螢幕用 `WINDOW_MODE_EXCLUSIVE_FULLSCREEN`（官方建議：較佳效能、較低輸入延遲）；提供 F11／Alt+Enter 切換：

```gdscript
func _input(event: InputEvent) -> void:
    if event.is_action_pressed("toggle_fullscreen"):
        var mode := DisplayServer.window_get_mode()
        if mode == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN \
                or mode == DisplayServer.WINDOW_MODE_FULLSCREEN:
            DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
        else:
            DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN)
```

- 預設 windowed 3x（1080p 螢幕下 640×360 的整數倍），`aspect=keep`。

### 9.3 檔案瘦身階梯（只在正式發行才做）

官方 template 基準：Windows 約 93 MB（zip 後 ~30 MB）、Web 約 42 MB（gzip 後 ~9 MB）——**jam／demo 直接用官方 template 即可**。正式發行 web 版才走自編階梯：

1. 自編 export template：`scons platform=windows target=template_release optimize=size lto=full`
2. `disable_3d=yes`
3. 模組白名單（`modules_enabled_by_default=no` ＋逐一啟用 gdscript／freetype／godot_physics_2d…）
4. Build profile：編輯器 `Project → Tools → Engine Compilation Configuration Editor` 勾掉不用的類別，`build_profile=xxx.build` 餵 scons
5. 最後一哩：Windows 過 UPX（防毒誤判風險）；Web 用 Brotli 預壓縮（可到 gzip < 5 MB）

其他：Export 對話框過濾 `*.psd` 等工作檔；Web 匯出把 Extensions Support 與 Thread Support 關掉可少載一份 wasm 變體。

---

## §10 工具生態一覽

| 工具 | 一句用途 | 出處 |
|---|---|---|
| **AsepriteWizard**（v9.8） | Aseprite 檔直接匯入 Godot（sprite sheet／動畫自動轉 SpriteFrames），美術改檔即時同步 | Godot Asset Library／GitHub（viniciusgerevini/godot-aseprite-wizard） |
| **Importality** | 多格式像素美術匯入器（Aseprite／Krita／Pixelorama 等來源統一進 Godot） | Godot Asset Library／GitHub |
| **Pixelorama** | 免費開源像素美術編輯器（本身用 Godot 寫的），無 Aseprite 授權時的替代 | Orama Interactive（GitHub／itch.io） |
| **Laigter** | 拖圖自動生成 normal/parallax/specular/occlusion map，可即時預覽打光；像素 sprite 批產 normal 首選（§6.5） | azagaya（GitHub／itch.io），v1.13.1 活躍維護中 |
| **Better Terrain** | 補齊內建 terrain 演算法缺陷的 autotile 外掛，執行期改地形必裝（§4.2）；直接支援 TileMapLayer | Portponky/better-terrain（MIT） |
| **LimboAI** | Behavior Tree ＋ State Machine 外掛，敵人／NPC AI 超出簡單 state machine 時用 | limbonaut/limboai（GitHub／Asset Library） |
| **unfake.js** | 把 AI 產的「偽像素圖」重建為真像素格（偵測實際格距、重採樣、減色） | GitHub（jenissimo/unfake.js）；AI 產圖管線細節 → pixel-game-scene-pipeline skill |

---

## §11 邊界與互鏈

本指南**不含**以下主題，需要時路由：

| 主題 | 去處 |
|---|---|
| AI 產圖場景方法論（設計先行、整張生成→摳件、並排驗收） | `pixel-game-scene-pipeline` Skill |
| 像素藝術基本功（色板、抗鋸齒、輪廓、dithering 手繪原則） | `pixel-game-scene-pipeline` Skill 的 `References/pixel-art-fundamentals.md` |
| AI 像素工具（產圖模型、後處理工具鏈） | `pixel-game-scene-pipeline` Skill 的 `References/ai-pixel-art-tools.md` |
| GDScript 工程紀律（強型別、節點架構、程式碼審查） | `godot-gameplay-scripter` agent |
| Shader 配方完整實作與特效 | `godot-shader-developer` agent＋godotshaders.com |
| 類型玩法系統（RPG／塔防／策略／4X／平台／Roguelike／視覺小說） | 本 skill 七份類型指南（見 SKILL.md 路由表） |


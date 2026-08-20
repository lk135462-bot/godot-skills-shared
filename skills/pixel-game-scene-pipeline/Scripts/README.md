# Scripts — 管線工具（可直接執行）

SKILL.md §4 工具鏈裡**這三支有現成程式碼**，其餘幾支只給行為契約規格（見 §4 表格「要點」欄，
那一欄才是踩過坑後定下來的部分，自行實作時照著做）。

```bash
pip install pillow numpy scipy     # scipy 只有 key_object.py 需要
```

三支都以 CLI 參數驅動、不寫死任何專案路徑，跨平台（Windows／macOS／Linux）。

---

## `cut_iso_objects.py` — 從整層底圖原位摳互動件

管線 §1 正面路線第 2–3 步的實作。互動件＝「疊在原位的複本」，底圖上物件仍在，
引擎只在 anchor 座標蓋上互動件或它的差分（燈亮／燈暗／使用中）。

```bash
# 1. 摳圖 → <outdir>/*.png + anchors.json
python cut_iso_objects.py cut    --spec art/objects_iso/cut_spec.json --outdir art/objects_iso

# 2. 人眼驗證多邊形畫對沒（左：描邊疊圖＋座標格線／右：棋盤格摳圖）
python cut_iso_objects.py verify --spec art/objects_iso/cut_spec.json --verify-dir tmp/cut_verify

# 3. 機械自檢：每件貼回底圖，逐像素 diff 必須 = 0
python cut_iso_objects.py check  --spec art/objects_iso/cut_spec.json --outdir art/objects_iso
```

**`check` 的 diff=0 是整條管線的正確性錨**——它保證「摳出來的就是原圖那一塊」。
沒過就不要往下走，後面所有差分都會歪。`check` 的 exit code 可直接串進 CI／一鍵驗收腳本。

spec 格式：

```json
{
  "source": "../rooms/public_floor.png",
  "objects": {
    "sofa":  {"polygon": [[120,880],[300,880],[300,1010],[120,1010]], "note": "客廳沙發"},
    "shelf": {"polygon": [[...]], "subtract": [[[...]]]}
  }
}
```

- 座標一律為**底圖原座標系**，原點左上。
- `source` 相對於 `--root`（預設＝spec 檔所在目錄）。
- `subtract` 可選，用來挖洞（避開擋在前面的靜態小物）。
- 輸出的 `anchors.json` 帶每件的 `x/y/w/h/z`，`z` ＝底邊 y，可直接當 painter's algorithm 的排序鍵。

**摳圖鐵則**：多邊形要完整包住物件（**絕不切進本體**）、不得含入其他互動件；
可含少量貼邊背景像素——原位貼回時像素恆等，不影響。

---

## `key_object.py` — 單色 key 底單物件去背

給「離散物件」路線用（見 §1 決策樹）。物件尺寸各異，所以**不套固定畫布、不做高度正規化**，
輸出原生比例 RGBA，由引擎依高度縮放。

```bash
python key_object.py raw/ --out art/objects                      # 整夾，預設洋紅 #FF00FF
python key_object.py raw/sofa.png --out art/objects --key 00FF00 # 綠幕
python key_object.py raw/ --out art/objects --pad 4              # 四邊留 4px 透明邊
```

做三件事：key 色去背（de-blend ＋ 邊緣 despill）→ 去雜點（**保留所有夠大的連通域**，
所以多件式物件如椅子＋抱枕不會被切掉一半）→ 貼齊內容邊界裁切，底列＝接地線。

`--key` 支援任何高飽和純色，不限洋紅。

---

## `make_tile.py` — 滿版材質 → 四向無縫 tile

不去背、不裁切。給地板／牆面鋪面用。

```bash
# 產 tile 並順便出 4x4 平鋪驗縫圖
python make_tile.py texture.png --out art/objects --name floor_wood.png --size 200 --test check.png

# 只對既有 tile 產平鋪測試圖
python make_tile.py --tiletest art/objects/floor_wood.png --test check.png --rep 4

# 材質是在 key 底上生成的、邊角有殘留亮點時
python make_tile.py texture.png --out art/objects --name wall.png --despill
```

**為什麼用梯度修正而不是常見的半格位移融合**：半格融合（offset 50%、混合接縫處）會在圖中央
留下鬼影，強紋理材質還會出現對角干涉條紋。梯度修正是把「左右邊差值」沿整個寬度線性攤平，
只加一層低頻修正，**原始紋理完全保留**——木地板這類強紋理也不會糊掉板紋。

兩個實作細節，錯了就白做（都經量測驗證）：

1. **修正量取「右 − 左」不是「左 − 右」**——要讓兩邊各走一半、收斂到中點。
   方向寫反會把接縫**放大 1.5 倍**（實測：未處理邊差 31.6 → 寫反後 47.5 → 正確 0.0）。
   近均勻材質看不出來，強紋理一平鋪就現形。
2. **先縮放、再做無縫**——LANCZOS 重採樣的取樣核不會繞回對邊。先無縫再縮放，
   縮完邊緣又對不上（實測 256→128 把 0 的邊差變回 3.5）。

**驗收**：開 `--test` 產出的平鋪圖放大看，**有規律直線／橫線＝接縫沒消掉**。

---

## 沒有現成程式碼的那幾支

§4 表格裡另外幾支只給規格，原因寫在這裡：

- **底圖外擴**（§4 的外擴範式）——高度綁定「那一張圖」：畫布尺寸、外擴寬度、
  從原圖實測出來的調色盤 RGB、剪影帶 y 座標全是該圖專屬。**方法可複用，程式碼不能**。
  要點在 §4：原圖最後整張貼回新畫布 → 裁回 diff=0 天生保證；記錄 offset，anchors 全體平移即可沿用。
- **產圖批次調度**（§4 的 dispatcher）——綁定特定產圖 CLI 工具。要點在 §4：
  本進程親自 spawn 子進程（exit code ＝死活，不用猜）＋台帳單一寫者防重複發包＋
  額度上限熔斷停發、留 resume 點重跑即續。
- **一鍵驗收**（專案專屬驗收腳本）——1,500 行綁死專案的場景、角色、zone 系統。
  範式在 §5：參數化、headless parse 前哨、`try/finally` 還原測試前狀態、
  `subprocess` 明定 `encoding='utf-8'`（Windows cp950 防線），搭 `REGRESSION_CHECKLIST.md` 分自動層＋目視層。

# -*- coding: utf-8 -*-
"""
make_tile — 把「滿版材質貼圖」做成四向無縫平鋪 tile（地板／牆面鋪面用）。

與 key_object 不同：tile **不去背、不裁切**。流程是

    讀滿版材質 → (可選) key 色殘留清除 → 縮到 tile 尺寸 → 梯度修正成四向無縫 → 存 RGBA

**為什麼用梯度修正而不是常見的半格位移融合**：半格融合（offset 50%、把接縫處混合）
會在圖中央留下鬼影，強紋理材質還會出現對角干涉條紋。梯度修正是把「左邊與右邊的差值」
沿整個寬度線性攤平，只加了一層低頻修正，**原始紋理完全保留**——近均勻材質（牆面）尤佳，
木地板這類強紋理也不會糊掉板紋。

用法：
    # 產 tile（並順便出 4x4 平鋪驗縫圖）
    python make_tile.py texture.png --out art/objects --name floor_wood.png --size 200 --test check.png

    # 只對既有 tile 產平鋪測試圖
    python make_tile.py --tiletest art/objects/floor_wood.png --test check.png --rep 4

驗收：開 `--test` 產出的平鋪圖，放大看**有沒有規律出現的直線／橫線**。有＝接縫沒消掉。

相依：pillow、numpy
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image


def seamless(arr):
    """梯度修正法：把「左-右邊」「上-下邊」的差值沿全幅線性攤平 → 四向無縫。

    只加低頻修正、保留原始紋理，不做半格融合 → 無鬼影／無對角干涉條紋。
    """
    a = arr.astype(np.float32)
    H, W = a.shape[:2]

    # 修正量取「右 - 左」，使左右兩邊各走一半、收斂到中點：
    #   new_left  = left  + 0.5*(right-left) = (left+right)/2
    #   new_right = right - 0.5*(right-left) = (left+right)/2
    # 寫成 (left-right)/2 會讓兩邊反向拉開，接縫反而放大 1.5 倍。
    dh = a[:, W - 1, :] - a[:, 0, :]                    # 左右邊差（每列每通道）
    tx = np.linspace(0.0, 1.0, W)[None, :, None]
    a = a + (0.5 - tx) * dh[:, None, :]                 # 沿寬攤平 → 左邊 = 右邊

    # 垂直修正在水平之後做；此時第 0 欄與第 W-1 欄已相同，
    # 故 dv[0] == dv[W-1]，水平無縫不會被破壞。
    dv = a[H - 1, :, :] - a[0, :, :]                    # 上下邊差
    ty = np.linspace(0.0, 1.0, H)[:, None, None]
    a = a + (0.5 - ty) * dv[None, :, :]                 # 沿高攤平 → 上邊 = 下邊

    return np.clip(a, 0, 255).astype(np.uint8)


def parse_rgb(s):
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"顏色需為 6 位 hex，收到：{s}")
    return [int(s[i:i + 2], 16) for i in (0, 2, 4)]


def despill_key(arr, key_hex, to_hex):
    """清除 key 色殘留亮點。

    材質若是在 key 底（如洋紅 #FF00FF）上生成的，邊角可能殘留幾顆 key 色像素，
    平鋪後會變成規律亮點。這裡把它們換成指定的中性色。

    ⚠ 預設不啟用——因為材質本身可能就含有接近 key 色的正當像素（霓虹招牌、
    紫色布料）。只有確定材質是 key 底生成的才加 `--despill`。
    """
    kr, kg, kb = parse_rgb(key_hex)
    a = arr.astype(np.float32)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    # 依 key 色的高/低通道判定，而非寫死洋紅
    hi = [c for c, v in zip((R, G, B), (kr, kg, kb)) if v >= 128]
    lo = [c for c, v in zip((R, G, B), (kr, kg, kb)) if v < 128]
    if not hi or not lo:
        raise ValueError("key 色必須是高飽和純色（如 FF00FF、00FF00）")
    mask = np.logical_and.reduce([c > 180 for c in hi] + [c < 120 for c in lo])
    n = int(mask.sum())
    if n:
        a[mask] = np.array(parse_rgb(to_hex), dtype=np.float32)
        print(f"[despill] 清除 {n} 顆 key 色殘留像素 -> #{to_hex.lstrip('#').upper()}")
    return a.astype(np.uint8)


def make(input_path, size, despill=None, despill_to="785A46"):
    """順序很重要：**先縮放、再做無縫**。

    LANCZOS 重採樣的取樣核不會繞回對邊，所以先做無縫再縮放，縮完邊緣又會對不上
    （實測 256→128 會把 0 的邊差變回 3.5）。縮完才修，最終輸出才真的無縫。
    """
    im = Image.open(input_path).convert("RGB")
    arr = np.array(im)
    if despill:
        arr = despill_key(arr, despill, despill_to)
    if size and size != arr.shape[1]:
        arr = np.array(Image.fromarray(arr, "RGB").resize((size, size), Image.LANCZOS))
    arr = seamless(arr)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def tile_test(tile_img, rep, out_path):
    w, h = tile_img.size
    canvas = Image.new("RGBA", (w * rep, h * rep))
    for j in range(rep):
        for i in range(rep):
            canvas.paste(tile_img, (i * w, j * h))
    canvas.convert("RGB").save(out_path)
    print(f"[tiletest] {rep}x{rep} -> {out_path}  ({canvas.size[0]}x{canvas.size[1]})")
    print("           放大看有無規律直線／橫線；有＝接縫沒消掉")


def main():
    ap = argparse.ArgumentParser(description="滿版材質 → 四向無縫 tile")
    ap.add_argument("input", nargs="?", help="輸入滿版材質 PNG")
    ap.add_argument("--out", help="輸出資料夾")
    ap.add_argument("--name", help="輸出檔名（如 floor_wood.png）")
    ap.add_argument("--size", type=int, default=200, help="tile 邊長 px（預設 200）")
    ap.add_argument("--test", help="順便輸出 NxN 平鋪驗縫圖到此路徑")
    ap.add_argument("--rep", type=int, default=4, help="平鋪測試圖的重複數（預設 4）")
    ap.add_argument("--tiletest", help="只對既有 tile 產平鋪測試圖，不做其他處理")
    ap.add_argument("--despill", nargs="?", const="FF00FF", default=None,
                    help="清除 key 色殘留（材質是 key 底生成時才需要）。可指定 hex，預設 FF00FF")
    ap.add_argument("--despill-to", default="785A46", help="殘留像素換成的顏色 hex（預設中性暖木色）")
    a = ap.parse_args()

    if a.tiletest:
        tile = Image.open(a.tiletest).convert("RGBA")
        tile_test(tile, a.rep, a.test or "tiletest.png")
        return 0

    if not a.input:
        ap.error("需要輸入檔，或改用 --tiletest")

    tile = make(a.input, a.size, despill=a.despill, despill_to=a.despill_to)
    if a.out and a.name:
        os.makedirs(a.out, exist_ok=True)
        dst = os.path.join(a.out, a.name)
        tile.save(dst)
        print(f"[tile] {a.name}  {tile.size[0]}x{tile.size[1]}  -> {dst}")
    elif a.out or a.name:
        ap.error("--out 與 --name 要一起給")
    if a.test:
        tile_test(tile, a.rep, a.test)
    return 0


if __name__ == "__main__":
    sys.exit(main())

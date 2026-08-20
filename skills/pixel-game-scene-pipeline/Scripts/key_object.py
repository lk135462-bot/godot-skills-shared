# -*- coding: utf-8 -*-
"""
key_object — 把「單色 key 底的單物件圖」去背成透明 PNG。

給「離散物件」路線用（見 SKILL.md §1 決策樹）：物件尺寸各異（沙發寬、瑜珈球小），
所以**不套固定人物畫布、不做高度正規化**，只做三件事：

  1. key 色去背（de-blend ＋ 邊緣 despill）
  2. 去雜點——保留所有夠大的連通域，**支援多件式物件**（例如椅子＋抱枕算同一件）
  3. 貼齊內容邊界裁切，底列＝接地線

輸出原生比例 RGBA，由引擎依高度縮放（慣例：`draw(img, x - w/2, baseY - h, w, h)`）。

用法：
    python key_object.py <輸入夾或檔...> --out <輸出夾> [--pad 2] [--key FF00FF]

範例：
    python key_object.py raw/ --out art/objects
    python key_object.py raw/sofa.png raw/chair.png --out art/objects --key 00FF00

相依：pillow、numpy、scipy
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image
import scipy.ndimage as ndi


def parse_key(s):
    """'FF00FF' / '#FF00FF' / '00FF00' → np.array([R, G, B])"""
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"key 色需為 6 位 hex，收到：{s}")
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def dekey(path, key):
    """key 色去背 → (RGB float, alpha 0..1)，含 de-blend ＋ 邊緣 despill。

    做法：找出 key 色相對於其他色的「特徵差」，據此估 alpha，再把 key 色從
    半透明邊緣像素裡解出來（de-blend），最後壓掉邊緣殘留的色溢（despill）。
    """
    im = np.array(Image.open(path).convert("RGB")).astype(np.float32)
    R, G, B = im[:, :, 0], im[:, :, 1], im[:, :, 2]

    # key 色的兩個主通道 vs 弱通道的差：key 底→大正值，一般物件色→負值
    hi = [i for i, v in enumerate(key) if v >= 128]
    lo = [i for i, v in enumerate(key) if v < 128]
    if not hi or not lo:
        raise ValueError("key 色必須是高飽和純色（如 FF00FF、00FF00、0000FF）")
    chans = [R, G, B]
    hi_min = np.minimum.reduce([chans[i] for i in hi])
    lo_max = np.maximum.reduce([chans[i] for i in lo])
    kdiff = hi_min - lo_max

    alpha = np.clip((150.0 - kdiff) / 90.0, 0.0, 1.0)
    a3 = alpha[:, :, None]
    safe = np.where(a3 < 0.02, 1.0, a3)
    true = np.clip((im - (1.0 - a3) * key.astype(np.float32)) / safe, 0, 255)

    # despill：半透明邊緣上，若仍偏向 key 色的色相就把溢出量減掉
    t = [true[:, :, 0], true[:, :, 1], true[:, :, 2]]
    t_hi_mean = np.mean([t[i] for i in hi], axis=0)
    t_lo_max = np.maximum.reduce([t[i] for i in lo])
    spill = np.clip(t_hi_mean - t_lo_max, 0, None)
    edge = (alpha < 0.95) & (alpha > 0.02)
    over = edge & (t_hi_mean > t_lo_max)
    for i in hi:
        true[:, :, i] = np.where(over, t[i] - spill, t[i])

    return np.clip(true, 0, 255), alpha


def keep_significant(alpha, thr=0.35, min_frac=0.002):
    """保留所有面積 >= min_frac × 總畫素的連通域，只丟真正的小雜點。

    用連通域而非「只留最大塊」，是為了支援多件式物件；若全部都太小則保底留最大塊。
    """
    mask = alpha > thr
    lbl, n = ndi.label(mask)
    if n == 0:
        return alpha
    sizes = ndi.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    min_px = max(64, min_frac * alpha.size)
    keep = {i + 1 for i, s in enumerate(sizes) if s >= min_px}
    if not keep:
        keep = {int(np.argmax(sizes)) + 1}
    out = alpha.copy()
    out[~np.isin(lbl, list(keep))] = 0.0
    return out


def key_one(path, key, pad=2):
    rgb, alpha = dekey(path, key)
    alpha = keep_significant(alpha)
    ys, xs = np.where(alpha > 0.16)
    if len(ys) == 0:
        raise ValueError(f"空圖（去背後無內容）: {path}")
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    rgba = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    crop = rgba[y0:y1 + 1, x0:x1 + 1]
    # 四邊各留 pad 透明邊；底邊也留，引擎以最底「不透明列」對齊仍是接地線，
    # pad 只是防裁切太緊導致邊緣被削。
    if pad > 0:
        h, w = crop.shape[:2]
        canvas = np.zeros((h + 2 * pad, w + 2 * pad, 4), dtype=np.uint8)
        canvas[pad:pad + h, pad:pad + w] = crop
        crop = canvas
    return Image.fromarray(crop, "RGBA")


def main():
    ap = argparse.ArgumentParser(description="單色 key 底單物件去背")
    ap.add_argument("inputs", nargs="+", help="輸入 PNG 檔或資料夾（資料夾會取其中所有 *.png）")
    ap.add_argument("--out", required=True, help="輸出資料夾")
    ap.add_argument("--pad", type=int, default=2, help="四邊保留的透明邊（px，預設 2）")
    ap.add_argument("--key", default="FF00FF", help="key 色 hex，預設 FF00FF（洋紅）")
    a = ap.parse_args()

    key = parse_key(a.key)
    os.makedirs(a.out, exist_ok=True)

    files = []
    for inp in a.inputs:
        if os.path.isdir(inp):
            files += sorted(glob.glob(os.path.join(inp, "*.png")))
        else:
            files.append(inp)
    if not files:
        print("[key_object] 沒有找到任何 PNG")
        return 1

    print(f"[key_object] {len(files)} 檔 -> {a.out}  key=#{a.key.lstrip('#').upper()} pad={a.pad}")
    fails = 0
    for f in files:
        name = os.path.basename(f)
        try:
            img = key_one(f, key, pad=a.pad)
            img.save(os.path.join(a.out, name))
            print(f"  OK   {name}  {img.size[0]}x{img.size[1]}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            fails += 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

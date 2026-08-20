# -*- coding: utf-8 -*-
"""
cut_iso_objects — 從整層場景底圖「原位摳」互動件（多邊形硬邊遮罩，保留原圖光影）。

這是 SKILL.md §1 正面管線第 2–3 步的實作：**整張全生成 → 原位摳互動件 → 引擎疊層**。

核心概念：互動件＝「疊在原位的複本」。底圖上物件仍然在，引擎只是在 anchor 座標
蓋上互動件或它的差分（燈亮／燈暗／使用中）。因此遮罩可以含少量貼邊背景像素——
原位合成時像素恆等，差分只改物件像素、背景像素原樣保留。

**摳圖鐵則**：多邊形必須完整包住物件（絕不切進本體）、不得含入其他互動件。

三個模式：
    cut     依 spec 摳圖 → <outdir>/*.png ＋ anchors.json
    verify  產每件「描邊疊圖（帶座標格線）＋棋盤格摳圖」的並排驗證圖，人眼確認多邊形畫對
    check   機械自檢：每件按 anchor 貼回底圖，**逐像素 diff 必須為 0**

`check` 的 diff=0 是整條管線的正確性錨——它保證「摳出來的就是原圖那一塊」。
沒過就不要往下走，後面所有差分都會歪。

spec 格式（JSON）：
    {
      "source": "art/rooms/public_floor.png",
      "objects": {
        "sofa":  {"polygon": [[120,880],[300,880],[300,1010],[120,1010]], "note": "客廳沙發"},
        "shelf": {"polygon": [[...]], "subtract": [[[...]]]}
      }
    }
- 座標一律為**底圖原座標系**，原點左上。
- `subtract` 可選，用來挖洞（例如避開擋在前面的靜態小物）。
- `source` 相對於 `--root`（預設為 spec 檔所在目錄）。

用法：
    python cut_iso_objects.py cut    --spec art/objects_iso/cut_spec.json --outdir art/objects_iso
    python cut_iso_objects.py verify --spec art/objects_iso/cut_spec.json --verify-dir tmp/cut_verify
    python cut_iso_objects.py check  --spec art/objects_iso/cut_spec.json --outdir art/objects_iso

exit code：`check` 全過回 0，有不合格回 1（可直接串進 CI／一鍵驗收腳本）。

相依：pillow、numpy
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 跨平台字型 fallback：verify 模式的座標標籤用，找不到就用 PIL 內建點陣字
FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(sz=20):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def load(spec_path, root=None):
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    root = root or os.path.dirname(os.path.abspath(spec_path))
    src_path = os.path.join(root, spec["source"])
    if not os.path.isfile(src_path):
        raise SystemExit(f"[ERR] 找不到底圖：{src_path}\n     （spec 的 source 相對於 --root，目前 root={root}）")
    return spec, Image.open(src_path).convert("RGBA"), root


def poly_mask(size, polygon, subtract=None):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.polygon([tuple(p) for p in polygon], fill=255)
    for sub in (subtract or []):
        d.polygon([tuple(p) for p in sub], fill=0)   # 挖洞
    return m


def cmd_cut(spec, src, outdir):
    os.makedirs(outdir, exist_ok=True)
    anchors = {}
    for name, obj in spec["objects"].items():
        poly = obj["polygon"]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, y0 = max(0, min(xs)), max(0, min(ys))
        x1, y1 = min(src.width, max(xs)), min(src.height, max(ys))
        mask = poly_mask(src.size, poly, obj.get("subtract")).crop((x0, y0, x1, y1))
        piece = src.crop((x0, y0, x1, y1))
        piece.putalpha(mask)                          # 硬邊 0/255，不羽化（像素風）
        piece.save(os.path.join(outdir, name + ".png"))
        anchors[name] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                         "z": y1}                     # painter's sort key = 底邊 y，小者先畫
        if obj.get("note"):
            anchors[name]["note"] = obj["note"]
        print(f"[CUT] {name:16s} bbox=({x0},{y0},{x1 - x0},{y1 - y0})")

    meta = {"source": spec["source"], "canvas": [src.width, src.height],
            "coord_system": "source image pixels, origin top-left",
            "objects": anchors}
    with open(os.path.join(outdir, "anchors.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[OK] {len(anchors)} 件 + anchors.json -> {outdir}")
    return 0


def cmd_verify(spec, src, verify_dir):
    os.makedirs(verify_dir, exist_ok=True)
    Z = 2        # 放大倍率
    PAD = 36     # 物件外圍多顯示的範圍
    F = _font(20)
    for name, obj in spec["objects"].items():
        poly = obj["polygon"]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        l, t = max(0, min(xs) - PAD), max(0, min(ys) - PAD)
        r, b = min(src.width, max(xs) + PAD), min(src.height, max(ys) + PAD)

        # 左半：描邊疊圖（16px 格線，每 32px 標座標）
        crop = src.crop((l, t, r, b)).convert("RGB").resize(((r - l) * Z, (b - t) * Z), Image.NEAREST)
        d = ImageDraw.Draw(crop)
        for gx in range(l - l % 16, r + 1, 16):
            X = (gx - l) * Z
            major = gx % 32 == 0
            d.line([(X, 0), (X, crop.height)], fill=(0, 200, 200) if major else (0, 90, 90), width=1)
        for gy in range(t - t % 16, b + 1, 16):
            Y = (gy - t) * Z
            major = gy % 32 == 0
            d.line([(0, Y), (crop.width, Y)], fill=(0, 200, 200) if major else (0, 90, 90), width=1)
        for gx in range(l - l % 32, r + 1, 32):
            X = (gx - l) * Z
            for ty in (2, crop.height - 26):
                d.rectangle([X + 1, ty, X + 52, ty + 22], fill=(0, 0, 0))
                d.text((X + 3, ty), str(gx), fill=(255, 255, 0), font=F)
        for gy in range(t - t % 32, b + 1, 32):
            Y = (gy - t) * Z
            for tx in (2, crop.width - 58):
                d.rectangle([tx, Y + 1, tx + 54, Y + 23], fill=(0, 0, 0))
                d.text((tx + 2, Y + 1), str(gy), fill=(0, 255, 120), font=F)
        pts = [((p[0] - l) * Z, (p[1] - t) * Z) for p in poly]
        d.polygon(pts, outline=(255, 0, 60))
        d.polygon([(x + 1, y) for x, y in pts], outline=(255, 0, 60))   # 加粗
        for x, y in pts:
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 0, 60))

        # 右半：棋盤格底上的摳圖（看透明區有沒有切進本體）
        mask = poly_mask(src.size, poly, obj.get("subtract")).crop((l, t, r, b))
        piece = src.crop((l, t, r, b))
        piece.putalpha(mask)
        piece = piece.resize(crop.size, Image.NEAREST)
        checker = Image.new("RGB", crop.size, (90, 90, 90))
        cd = ImageDraw.Draw(checker)
        for cy in range(0, crop.size[1], 16):
            for cx in range(0, crop.size[0], 16):
                if (cx // 16 + cy // 16) % 2 == 0:
                    cd.rectangle([cx, cy, cx + 15, cy + 15], fill=(130, 130, 130))
        checker.paste(piece, (0, 0), piece)

        combo = Image.new("RGB", (crop.width * 2 + 8, crop.height), (20, 20, 24))
        combo.paste(crop, (0, 0))
        combo.paste(checker, (crop.width + 8, 0))
        out = os.path.join(verify_dir, f"v_{name}.png")
        combo.save(out)
        print(f"[VER] {name} -> {out}")
    return 0


def cmd_check(spec, src, outdir):
    anchors_path = os.path.join(outdir, "anchors.json")
    if not os.path.isfile(anchors_path):
        raise SystemExit(f"[ERR] 找不到 {anchors_path}，請先跑 cut")
    with open(anchors_path, encoding="utf-8") as f:
        anchors = json.load(f)["objects"]

    base = np.array(src)
    bad = 0
    for name, a in anchors.items():
        piece = Image.open(os.path.join(outdir, name + ".png")).convert("RGBA")
        if (piece.width, piece.height) != (a["w"], a["h"]):
            print(f"[FAIL] {name}: 尺寸 {piece.size} != anchor ({a['w']},{a['h']})")
            bad += 1
            continue
        p = np.array(piece)
        region = base[a["y"]:a["y"] + a["h"], a["x"]:a["x"] + a["w"]]
        opaque = p[:, :, 3] == 255
        diff = (p[:, :, :3][opaque] != region[:, :, :3][opaque]).any(axis=-1).sum()
        semi = ((p[:, :, 3] != 0) & (p[:, :, 3] != 255)).sum()
        status = "OK  " if diff == 0 and semi == 0 else "FAIL"
        if status == "FAIL":
            bad += 1
        print(f"[{status}] {name:16s} 不透明px={int(opaque.sum()):7d} "
              f"原位diff={int(diff)} 半透明px={int(semi)}")

    print("[ALL PASS] 全件原位貼回像素恆等" if bad == 0 else f"[NG] {bad} 件不合格")
    return bad


def main():
    ap = argparse.ArgumentParser(description="從整層底圖原位摳互動件")
    ap.add_argument("mode", choices=["cut", "verify", "check"])
    ap.add_argument("--spec", required=True, help="cut_spec.json 路徑")
    ap.add_argument("--root", help="spec 內 source 的相對基準目錄（預設＝spec 檔所在目錄）")
    ap.add_argument("--outdir", help="摳圖輸出／讀取目錄（cut 與 check 用，預設＝spec 檔所在目錄）")
    ap.add_argument("--verify-dir", default="tmp/cut_verify", help="verify 圖輸出目錄")
    a = ap.parse_args()

    spec, src, root = load(a.spec, a.root)
    outdir = a.outdir or os.path.dirname(os.path.abspath(a.spec))

    if a.mode == "cut":
        return cmd_cut(spec, src, outdir)
    if a.mode == "verify":
        return cmd_verify(spec, src, a.verify_dir)
    return 1 if cmd_check(spec, src, outdir) else 0


if __name__ == "__main__":
    sys.exit(main())

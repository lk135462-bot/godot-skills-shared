# 第三方內容署名與授權（NOTICE）

本 repo 收錄了數個第三方開源專案的原文。**散布或再散布本 repo 的衍生物時，須遵守以下各授權條款。**

## 收錄清單

| 目錄 | 來源 | 授權 | 取得版本 |
|---|---|---|---|
| `skills/godot-game-dev/References/vendor/godotprompter/` | [jame581/GodotPrompter](https://github.com/jame581/GodotPrompter) v1.13.2 | MIT | eae755a（clone @ 2026-08-17）|
| `skills/godot-game-dev/References/vendor/terma-godot/`<br>`skills/godot-game-dev/References/vendor/terma-godot-interactive/` | [bfollington/terma](https://github.com/bfollington/terma)（`plugins/tsal/skills/`） | **CC-BY-SA-4.0** | GitHub API 抓取 @ 2026-08-17（main）|
| `skills/godot-game-dev/References/vendor/godot-headless/` | [biologicpro/godot_codex_skills](https://github.com/biologicpro/godot_codex_skills) | MIT | bf1a17a（clone @ 2026-08-17）|
| `skills/pixel-game-scene-pipeline/References/vendor-sprite-forge/` | [0x0funky/agent-sprite-forge](https://github.com/0x0funky/agent-sprite-forge) | MIT | 64fd0b5（clone @ 2026-08-17）|

各目錄內保留了原始 LICENSE 檔，**請勿移除**。

## CC-BY-SA-4.0 的額外義務（terma 部分）

`vendor/terma-godot/` 與 `vendor/terma-godot-interactive/` 採 CC-BY-SA-4.0：

1. **署名**：保留原作者與來源連結（本檔即為署名）
2. **相同方式分享**：若你**修改**了這兩個目錄的內容並散布，該衍生物須以 **CC-BY-SA-4.0 或相容授權**釋出
3. 未修改的原樣轉錄，仍須保留授權聲明

> 本 repo 的**原創內容**（各 `SKILL.md`、`References/godot-*.md`、`agents/*.md`）為獨立撰寫，
> 僅在文中「引用並標註出處」，不構成 vendor 內容的衍生作品；
> `godot-architecture-discipline.md`、`godot-file-format-safety.md`、`godot-verification-toolchain.md`
> 三份為情境適配摘要，已逐節標示出處，若你對其散布義務有疑慮，最保險的做法是整包以 CC-BY-SA-4.0 釋出。

## 已知原文勘誤（整合時查證）

- `vendor/godotprompter/2d-essentials.md` 將 `TileMapLayer` 標為 4.5+、`Parallax2D` 標為 4.4+ ——
  **兩者實為 Godot 4.3 引入**（該 repo 自己的 `references/tilemap.md` 與 brainstorming 表寫法正確）。引用時以 4.3 為準。
- `vendor-sprite-forge` 的 chroma 契約寫死洋紅 `#FF00FF`；若你的產線用別的 key 色需自行改參數。
- `vendor-sprite-forge` 的 `pixel_art` 風格檔並非真像素（無 downscale／quantize），真像素需求要在尾端接量化步驟。

# vendor-sprite-forge（2026-08-18 整合）

來源：https://github.com/0x0funky/agent-sprite-forge（MIT，LICENSE 在本目錄；來源 commit 64fd0b5 @ 2026-08-17）。

情境適配注意：
- 其 chroma 契約為洋紅 #FF00FF；**若你的既有系列用別的 key 色（如綠幕 #00FF00）**——用其腳本時需改 key 色或沿用自己的去背工具鏈。
- 其 pixel_art 風格檔非真像素（無 downscale／quantize）；真像素需求在尾端接本管線的量化步驟。
- 其 identity 鎖僅 prompt 工程；有 LoRA／ComfyUI 環境者可補強，anchor sheet 與 scale profile 概念與之互補。

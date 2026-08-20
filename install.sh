#!/usr/bin/env bash
# 把本 repo 的 Godot Skills 與 Agents 安裝到 Claude Code 設定目錄。
#
#   ./install.sh                  複製到 ~/.claude/{skills,agents}
#   ./install.sh --link           改用 symlink，之後 git pull 即同步
#   ./install.sh --target ./proj  裝進專案內的 .claude/ 而非家目錄
#   ./install.sh --force          覆蓋已存在的同名項目
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINK=0
FORCE=0
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --link)   LINK=1; shift ;;
    --force)  FORCE=1; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知參數：$1" >&2; exit 1 ;;
  esac
done

if [ -n "$TARGET" ]; then
  CLAUDE_DIR="$(cd "$TARGET" && pwd)/.claude"
else
  CLAUDE_DIR="$HOME/.claude"
fi

SKILLS_DIR="$CLAUDE_DIR/skills"
AGENTS_DIR="$CLAUDE_DIR/agents"
mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

echo "安裝目標：$CLAUDE_DIR"
echo "模式：$([ $LINK -eq 1 ] && echo 符號連結 || echo 複製)"
echo

install_item() {
  local src="$1" dest_dir="$2"
  local name dest
  name="$(basename "$src")"
  dest="$dest_dir/$name"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ $FORCE -eq 0 ]; then
      echo "  跳過 $name（已存在，用 --force 覆蓋）"
      return
    fi
    rm -rf "$dest"
  fi

  if [ $LINK -eq 1 ]; then
    ln -s "$src" "$dest"
    echo "  連結 $name"
  else
    cp -R "$src" "$dest"
    echo "  複製 $name"
  fi
}

echo "Skills："
for d in "$ROOT"/skills/*/; do
  install_item "${d%/}" "$SKILLS_DIR"
done

echo
echo "Agents："
for f in "$ROOT"/agents/*.md; do
  install_item "$f" "$AGENTS_DIR"
done

echo
echo "完成。在 Claude Code 用 /skills 與 /agents 確認載入狀況。"

#!/bin/bash
# 右クリックメニューに「請求書をリネーム」が出ないときの調査用。
# ターミナルで  bash 診断.command  として実行し、出力をそのまま共有してください。
set -uo pipefail
cd "$(dirname "$0")" || exit 1

BUNDLE="$HOME/Library/Services/請求書をリネーム.workflow"

echo "================================================"
echo " 請求書リネーム 診断レポート"
echo "================================================"
echo

echo "## 1. macOS"
sw_vers 2>/dev/null || echo "  (sw_vers なし: macOS ではありません)"
echo

echo "## 2. セットアップの状態"
if [ -x "./.venv/bin/doc-namer" ]; then
  echo "  ✓ doc-namer あり: $(pwd)/.venv/bin/doc-namer"
  if ./.venv/bin/doc-namer --help >/dev/null 2>&1; then
    echo "  ✓ doc-namer は実行できる"
  else
    echo "  ✗ doc-namer が実行できない"
  fi
else
  echo "  ✗ doc-namer がない（セットアップ.command が未実行）"
fi
echo

echo "## 3. クイックアクションのバンドル"
if [ -d "$BUNDLE" ]; then
  echo "  ✓ ある: $BUNDLE"
  echo "  中身:"
  find "$BUNDLE" -type f | sed 's|^|    |'
  echo
  echo "  plist の妥当性:"
  for f in "$BUNDLE/Contents/Info.plist" "$BUNDLE/Contents/document.wflow"; do
    if [ -f "$f" ]; then
      printf '    %s: ' "$(basename "$f")"
      plutil -lint "$f" 2>&1 | sed 's|.*: ||'
    else
      echo "    $(basename "$f"): ない"
    fi
  done
  echo
  echo "  メニュー名:"
  plutil -extract NSServices.0.NSMenuItem.default raw "$BUNDLE/Contents/Info.plist" 2>&1 | sed 's|^|    |'
  echo "  隔離属性(quarantine):"
  if xattr -l "$BUNDLE" 2>/dev/null | grep -q quarantine; then
    echo "    ✗ ついている（これがあるとサービスとして読まれないことがある）"
  else
    echo "    ✓ なし"
  fi
else
  echo "  ✗ ない: $BUNDLE"
  echo "  ~/Library/Services の中身:"
  ls -la "$HOME/Library/Services" 2>&1 | sed 's|^|    |'
fi
echo

echo "## 4. macOS がサービスとして認識しているか"
PBS="/System/Library/CoreServices/pbs"
if [ -x "$PBS" ]; then
  if "$PBS" -dump_pboard 2>/dev/null | grep -q "請求書をリネーム"; then
    echo "  ✓ 認識されている"
  else
    echo "  ✗ 認識されていない（登録が効いていない）"
  fi
else
  echo "  ? pbs が見つからない: $PBS"
fi
echo

echo "## 5. 他のクイックアクション（比較用）"
ls -1 "$HOME/Library/Services" 2>/dev/null | sed 's|^|    |' || echo "    (なし)"
echo

echo "================================================"
echo " ここまでの出力をそのまま貼り付けて共有してください"
echo "================================================"

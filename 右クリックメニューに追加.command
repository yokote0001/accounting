#!/bin/bash
# ダブルクリックすると、Finder の右クリックメニュー（クイックアクション）に
# 「請求書をリネーム」を追加します。macOS 専用です。
set -uo pipefail
cd "$(dirname "$0")" || exit 1

finish() {
  echo
  echo "----------------------------------------"
  read -r -n 1 -p "Enter キーでこのウィンドウを閉じます..."
  echo
  exit "${1:-0}"
}

echo "=============================="
echo " 右クリックメニューに追加"
echo "=============================="
echo

if [ "$(uname)" != "Darwin" ]; then
  echo "✗ この機能は macOS 専用です。"
  finish 1
fi

CMD="$(pwd)/.venv/bin/doc-namer"
if [ ! -x "$CMD" ]; then
  echo "✗ まだセットアップされていません。"
  echo "  先に「セットアップ.command」をダブルクリックしてください。"
  finish 1
fi

./.venv/bin/python tools/install_quick_action.py "$CMD" || finish 1

echo
echo "使い方:"
echo "  Finder で PDF またはフォルダを選び、右クリック →"
echo "  「クイックアクション」→「請求書をリネーム」"
echo
echo "  出力先のフォルダが自動で開きます。"
echo
echo "メニューに出てこないときは:"
echo "  システム設定 →「一般」→「ログイン項目と機能拡張」→「Finder機能拡張」"
echo "  （または「機能拡張」→「Finder」）で「請求書をリネーム」を有効にしてください。"
echo "  それでも出ない場合は、一度ログアウト／再ログインすると反映されます。"
finish 0

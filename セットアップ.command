#!/bin/bash
# 最初に1回だけダブルクリックしてください。
# Python の仮想環境を作り、doc-namer コマンドを使えるようにします。
set -uo pipefail
cd "$(dirname "$0")" || exit 1

echo "=============================="
echo " doc-namer セットアップ"
echo "=============================="
echo

finish() {
  echo
  echo "----------------------------------------"
  read -r -n 1 -p "Enter キーでこのウィンドウを閉じます..."
  echo
  exit "${1:-0}"
}

# tomllib を使うので Python 3.11 以上が必要
PY=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "✗ Python 3.11 以上が見つかりませんでした。"
  echo
  echo "  https://www.python.org/downloads/macos/ から最新版をインストールしてから、"
  echo "  もう一度このファイルをダブルクリックしてください。"
  finish 1
fi

echo "使用する Python: $("$PY" --version) ($(command -v "$PY"))"
echo

echo "▸ 仮想環境を作成中..."
"$PY" -m venv .venv || { echo "✗ 仮想環境の作成に失敗しました。"; finish 1; }

echo "▸ 必要なライブラリをインストール中（初回は数分かかります）..."
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -e . --quiet || {
  echo "✗ インストールに失敗しました。ネットワーク接続を確認してください。"
  finish 1
}

echo
echo "✓ セットアップ完了"
echo
echo "  次からは「リネーム.command」をダブルクリックして使ってください。"
echo "  Finder の右クリックメニューに入れたい場合は"
echo "  「右クリックメニューに追加.command」をダブルクリックしてください。"
finish 0

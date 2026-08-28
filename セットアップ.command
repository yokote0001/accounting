#!/bin/bash
# 最初に1回だけ実行してください。
# Python の環境を用意し、Finder の右クリックメニューまで登録します。
#
# ダウンロードした .command は macOS 15 以降 Finder からは起動できません。
# ターミナルを開いて、次のように実行してください（bash と半角スペースを
# 打ってから、このファイルを Finder からドラッグして Enter）。
#
#   bash /path/to/セットアップ.command
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
  echo "  もう一度このファイルを実行してください。"
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

echo "✓ Python 環境の準備が完了しました"
echo

# 続けて Finder の右クリックメニューにも登録する。
# ここまで通れば、以降はターミナルを開く必要はない。
if [ "$(uname)" = "Darwin" ]; then
  echo "▸ Finder の右クリックメニューに登録中..."
  if ./.venv/bin/python tools/install_quick_action.py "$(pwd)/.venv/bin/doc-namer"; then
    echo
    echo "=============================="
    echo " ✓ すべて完了しました"
    echo "=============================="
    echo
    echo "使い方:"
    echo "  Finder で請求書の PDF を選び、右クリック →"
    echo "  「クイックアクション」→「請求書をリネーム」"
    echo
    echo "  選んだファイルがその場でリネームされます。"
    echo "  フォルダごと選んでも、複数選んでも大丈夫です。"
    echo
    echo "メニューに出てこないときは:"
    echo "  システム設定 →「一般」→「ログイン項目と機能拡張」→「Finder機能拡張」"
    echo "  で「請求書をリネーム」を有効にしてください。"
  else
    echo
    echo "✗ 右クリックメニューの登録に失敗しました。"
    echo "  ターミナルから doc-namer コマンドは使えます:"
    echo "    $(pwd)/.venv/bin/doc-namer <フォルダ> --move"
    finish 1
  fi
else
  echo "  （右クリックメニューの登録は macOS 専用のためスキップしました）"
fi
finish 0

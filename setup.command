#!/bin/bash
# 最初に1回だけ実行してください。
# Python の環境を用意し、Finder の右クリックメニューまで登録します。
#
# ダウンロードした .command は macOS 15 以降 Finder からは起動できません。
# ターミナルを開いて、次のように実行してください（bash と半角スペースを
# 打ってから、このファイルを Finder からドラッグして Enter）。
#
#   bash /path/to/setup.command
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

# ダウンロード / デスクトップ / 書類 フォルダは macOS に保護されていて、
# クイックアクションのプロセスからは中のプログラムを起動できない
# （Operation not permitted になる）。仮想環境を作る前に移しておく。
# 作ったあとだと、環境の中に古い場所が焼き込まれてしまい作り直しになる。
case "$(pwd)/" in
  "$HOME/Downloads/"*|"$HOME/Desktop/"*|"$HOME/Documents/"*)
    echo "⚠ このフォルダは macOS に保護された場所にあります。"
    echo "   $(pwd)"
    echo
    echo "  ここに置いたままだと、Finder の右クリックから実行できません。"
    echo "  ホームフォルダ直下に移すと解決します。"
    echo

    DEST="$HOME/$(basename "$(pwd)")"
    n=2
    while [ -e "$DEST" ]; do
      DEST="$HOME/$(basename "$(pwd)") ($n)"
      n=$((n + 1))
    done

    printf "移動しますか？ [Y/n]: "
    IFS= read -r move_answer
    case "$move_answer" in
      [Nn]*)
        echo
        echo "  移動せずに続けます。"
        echo "  ターミナルからは使えますが、右クリックメニューは動きません。"
        echo
        ;;
      *)
        if mv "$(pwd)" "$DEST" 2>/dev/null && cd "$DEST"; then
          echo "✓ 移動しました: $DEST"
          echo
        else
          echo "✗ 移動できませんでした。手動で移してからやり直してください:"
          echo "    mv \"$(pwd)\" \"$DEST\""
          finish 1
        fi
        ;;
    esac
    ;;
esac

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
    # Finder を再起動してサービス一覧を読み直させる。
    # Finder は自動で起動し直すので、デスクトップが一瞬消えるだけ。
    echo "▸ Finder を再読み込み中..."
    killall Finder 2>/dev/null || true

    # macOS が認識したかの目安。ここが空振りでも実際には
    # 使えることがあるので、警告は出すが手順は最後まで表示する。
    PBS="/System/Library/CoreServices/pbs"
    REGISTERED=1
    if [ -x "$PBS" ] && ! "$PBS" -dump_pboard 2>/dev/null | grep -q "請求書をリネーム"; then
      REGISTERED=0
    fi
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
    if [ "$REGISTERED" = "0" ]; then
      echo "※ macOS 側の登録確認は空振りでしたが、実際には使えることが多いです。"
      echo "  まず上の手順を試してください。"
      echo
    fi
    echo "メニューに出てこないときは、上から順に:"
    echo "  1. このフォルダの「請求書をリネーム.workflow」をダブルクリックし"
    echo "     「インストール」を押す"
    echo "  2. システム設定 →「一般」→「ログイン項目と機能拡張」→「Finder機能拡張」"
    echo "     で「請求書をリネーム」を有効にする"
    echo "  3. 一度ログアウトして入り直す"
    echo
    echo "  それでも駄目なら「bash check.command」の出力を共有してください。"
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

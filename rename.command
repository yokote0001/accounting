#!/bin/bash
# ダブルクリックすると、PDF の入ったフォルダ / ファイルを聞かれます。
# Finder からドラッグして Enter を押すと、その場でリネームします。
#
# 引数としてファイル / フォルダを渡すこともできます（右クリックメニューから呼ばれる形）。
set -uo pipefail
cd "$(dirname "$0")" || exit 1

CMD="./.venv/bin/doc-namer"
INTERACTIVE=1
[ -n "${DOC_NAMER_NONINTERACTIVE:-}" ] && INTERACTIVE=0

finish() {
  if [ "$INTERACTIVE" = "1" ]; then
    echo
    echo "----------------------------------------"
    read -r -n 1 -p "Enter キーでこのウィンドウを閉じます..."
    echo
  fi
  exit "${1:-0}"
}

if [ ! -x "$CMD" ]; then
  echo "✗ まだセットアップされていません。"
  echo "  先に「setup.command」をダブルクリックしてください。"
  finish 1
fi

# Finder からドラッグした文字列を実際のパスに戻す
# （前後の引用符を外し、バックスラッシュのエスケープを解除する）
unescape_path() {
  local raw="$1"
  raw="${raw#\"}"; raw="${raw%\"}"
  raw="${raw#\'}"; raw="${raw%\'}"
  printf '%s' "$raw" | sed 's/\\\(.\)/\1/g'
}

targets=("$@")

if [ "${#targets[@]}" -eq 0 ]; then
  echo "=============================="
  echo " 請求書・支払通知書のリネーム"
  echo "=============================="
  echo
  echo "PDF の入ったフォルダ（または PDF ファイル）を"
  echo "このウィンドウにドラッグして Enter を押してください。"
  echo
  printf "> "
  IFS= read -r line
  line="$(printf '%s' "$line" | sed 's/[[:space:]]*$//')"
  if [ -z "$line" ]; then
    echo "入力がありませんでした。"
    finish 1
  fi
  targets=("$(unescape_path "$line")")
fi

first="${targets[0]}"
if [ ! -e "$first" ]; then
  echo "✗ 見つかりません: $first"
  finish 1
fi

echo
echo "▸ こう変わります（この時点ではまだ何も書き込みません）"
echo "----------------------------------------"
"$CMD" "${targets[@]}" --move --dry-run
status=$?
echo "----------------------------------------"

if [ "$status" -ne 0 ]; then
  echo
  echo "※ [NG] と出たファイルは読み取れなかったものです。スキップされます。"
fi

echo
if [ "$INTERACTIVE" = "1" ]; then
  printf "この内容で出力しますか？ [y/N]: "
  IFS= read -r answer
  case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "中止しました。"; finish 0 ;;
  esac
fi

echo
"$CMD" "${targets[@]}" --move

echo
echo "✓ リネームしました"
if [ -d "$first" ]; then
  command -v open >/dev/null 2>&1 && open "$first"
else
  command -v open >/dev/null 2>&1 && open "$(dirname "$first")"
fi
finish 0

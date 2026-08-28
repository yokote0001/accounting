"""Finder の右クリックメニュー（クイックアクション）に「請求書をリネーム」を追加する。

Automator が書き出すのと同じ .workflow バンドルを
~/Library/Services/ に生成する。macOS 専用。
"""

from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SERVICE_NAME = "請求書をリネーム"
SERVICES_DIR = Path.home() / "Library" / "Services"

# クイックアクションが実行するシェルスクリプト。
# inputMethod=1（引数として渡す）なので、選択されたパスが "$@" に入る。
SHELL_SCRIPT = r"""#!/bin/bash
# Finder で選択された PDF を、その場でリネームする。
set -uo pipefail

# doc-namer の場所は設定ファイルから読む。
# こうしておくと、このバンドルをどこから入れても（配布物を
# ダブルクリックしてインストールしても）同じものが使える。
CONF="$HOME/.config/doc-namer/command"
if [ -r "$CONF" ]; then
  CMD="$(cat "$CONF")"
else
  CMD="{cmd}"
fi

LOG="$HOME/Library/Logs/doc-namer.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$CMD" ]; then
  osascript -e 'display alert "セットアップが必要です" message "先に setup.command を実行してください。"' >/dev/null 2>&1
  exit 1
fi

[ "$#" -eq 0 ] && exit 0

notify() {{
  osascript -e "display notification \"$1\" with title \"請求書をリネーム\"" >/dev/null 2>&1
}}

# --move --dry-run で「どう変わるか」を先に取る
plan=$("$CMD" "$@" --move --dry-run 2>/dev/null)
skipped=$("$CMD" "$@" --move --dry-run 2>&1 >/dev/null | grep -c "\[NG\]")

if [ -z "$plan" ]; then
  notify "リネームできる請求書・支払通知書がありませんでした"
  exit 0
fi

count=$(printf '%s\n' "$plan" | grep -c "^\[DRY\]")
names=$(printf '%s\n' "$plan" | sed 's/.*  ->  //' | while IFS= read -r p; do basename "$p"; done)
preview=$(printf '%s\n' "$names" | head -10)
[ "$count" -gt 10 ] && preview="$preview
… ほか $((count - 10)) 件"

message="$count 件をこの名前に変更します:

$preview"
[ "$skipped" -gt 0 ] && message="$message

（$skipped 件は読み取れないためそのままにします）"

answer=$(osascript -e "display dialog \"$(printf '%s' "$message" | sed 's/\\/\\\\/g; s/\"/\\\"/g')\" with title \"請求書をリネーム\" buttons {{\"キャンセル\", \"リネーム\"}} default button \"リネーム\"" 2>/dev/null)

case "$answer" in
  *リネーム*) ;;
  *) exit 0 ;;
esac

{{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  "$CMD" "$@" --move
}} >>"$LOG" 2>&1

notify "$count 件をリネームしました"
"""


def build_info_plist(service_uuid: str) -> dict:
    """Automator が書き出す Quick Action の Info.plist と同じ形にする。

    NSUUID / NSIconName / NSBackgroundColorName が無いと、サービスとして
    登録されても Finder のメニューに出てこないことがある。
    """
    return {
        "NSServices": [
            {
                "NSBackgroundColorName": "background",
                "NSIconName": "NSActionTemplate",
                "NSMenuItem": {"default": SERVICE_NAME},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
                "NSSendFileTypes": ["public.item"],
                "NSUUID": service_uuid,
            }
        ]
    }


def build_wflow(script: str, service_uuid: str) -> dict:
    input_uuid = str(uuid.uuid4()).upper()
    output_uuid = str(uuid.uuid4()).upper()
    action_uuid = str(uuid.uuid4()).upper()

    return {
        "AMApplicationBuild": "521",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "シェルスクリプトを実行",
                    "ActionParameters": {
                        "COMMAND_STRING": script,
                        "CheckedForUserDefaultShell": True,
                        # 1 = 入力を引数として渡す（"$@" で受け取る）
                        "inputMethod": 1,
                        "shell": "/bin/bash",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": input_uuid,
                    "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
                    "OutputUUID": output_uuid,
                    "UUID": action_uuid,
                    "UnlocalizedApplications": ["Automator"],
                    "arguments": {},
                    "isViewVisible": 1,
                    "location": "309.000000:253.000000",
                    "nibPath": (
                        "/System/Library/Automator/Run Shell Script.action"
                        "/Contents/Resources/Base.lproj/main.nib"
                    ),
                },
                "isViewVisible": 1,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            # Info.plist の NSUUID と一致させる
            "serviceUUID": service_uuid,
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 11,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


def install(
    cmd_path: Path,
    services_dir: Path = SERVICES_DIR,
    flush: bool = True,
    write_config: bool = True,
) -> Path:
    bundle = services_dir / f"{SERVICE_NAME}.workflow"
    contents = bundle / "Contents"

    if bundle.exists():
        shutil.rmtree(bundle)
    contents.mkdir(parents=True)

    if write_config:
        # doc-namer の場所を、バンドルから読める場所に控えておく
        conf = Path.home() / ".config" / "doc-namer" / "command"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(str(cmd_path), encoding="utf-8")

    service_uuid = str(uuid.uuid4()).upper()
    script = SHELL_SCRIPT.format(cmd=cmd_path)
    (contents / "Info.plist").write_bytes(plistlib.dumps(build_info_plist(service_uuid)))
    (contents / "document.wflow").write_bytes(plistlib.dumps(build_wflow(script, service_uuid)))

    if flush:
        # サービス一覧を再読み込みさせる。
        # pbs が無い環境でもバンドル自体は出来ているので、失敗しても続ける。
        pbs = "/System/Library/CoreServices/pbs"
        for args in ([pbs, "-flush"], [pbs, "-update"]):
            try:
                subprocess.run(args, check=False, capture_output=True)
            except OSError:
                pass
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finder のクイックアクションを追加する")
    parser.add_argument("command", help="doc-namer 実行ファイルのパス")
    parser.add_argument("--services-dir", default=str(SERVICES_DIR))
    parser.add_argument("--no-flush", action="store_true")
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="~/.config/doc-namer/command を書かない（配布用バンドルの生成時）",
    )
    args = parser.parse_args(argv)

    cmd_path = Path(args.command)
    if not args.no_config:
        cmd_path = cmd_path.resolve()
        if not cmd_path.exists():
            print(f"✗ 見つかりません: {cmd_path}", file=sys.stderr)
            return 1

    bundle = install(
        cmd_path,
        Path(args.services_dir),
        flush=not args.no_flush,
        write_config=not args.no_config,
    )
    print(f"✓ 追加しました: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

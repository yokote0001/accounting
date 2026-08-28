"""クイックアクション（.workflow バンドル）の生成テスト。"""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import install_quick_action as qa  # noqa: E402

pymupdf = pytest.importorskip("pymupdf")

from tests.test_cli import INVOICE_LINES, NOTICE_LINES, write_pdf  # noqa: E402


@pytest.fixture
def bundle(tmp_path):
    services = tmp_path / "Services"
    return qa.install(Path("/opt/doc-namer/bin/doc-namer"), services, flush=False)


def test_bundle_layout(bundle):
    assert (bundle / "Contents" / "Info.plist").is_file()
    assert (bundle / "Contents" / "document.wflow").is_file()
    assert bundle.name == "請求書をリネーム.workflow"


def test_info_plist_registers_a_finder_service(bundle):
    info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
    service = info["NSServices"][0]
    assert service["NSMenuItem"]["default"] == "請求書をリネーム"
    assert service["NSMessage"] == "runWorkflowAsService"
    assert service["NSRequiredContext"]["NSApplicationIdentifier"] == "com.apple.finder"
    assert service["NSSendFileTypes"] == ["public.item"]


def test_wflow_passes_selection_as_arguments(bundle):
    wflow = plistlib.loads((bundle / "Contents" / "document.wflow").read_bytes())
    action = wflow["actions"][0]["action"]
    params = action["ActionParameters"]
    assert action["BundleIdentifier"] == "com.apple.RunShellScript"
    # 1 = 入力を引数として渡す。0 だと標準入力になり "$@" が空になる
    assert params["inputMethod"] == 1
    assert params["shell"] == "/bin/bash"
    assert "/opt/doc-namer/bin/doc-namer" in params["COMMAND_STRING"]
    meta = wflow["workflowMetaData"]
    assert meta["workflowTypeIdentifier"] == "com.apple.Automator.servicesMenu"
    assert meta["serviceInputTypeIdentifier"] == "com.apple.Automator.fileSystemObject"


def test_install_replaces_an_existing_bundle(tmp_path):
    services = tmp_path / "Services"
    first = qa.install(Path("/old/doc-namer"), services, flush=False)
    (first / "Contents" / "stale.txt").write_text("x", encoding="utf-8")
    second = qa.install(Path("/new/doc-namer"), services, flush=False)
    assert not (second / "Contents" / "stale.txt").exists()
    wflow = plistlib.loads((second / "Contents" / "document.wflow").read_bytes())
    assert "/new/doc-namer" in wflow["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]


def _run_embedded(services, work, targets, answer="リネーム"):
    """バンドルに埋め込まれたシェルスクリプトを、osascript を差し替えて動かす。"""
    wflow = plistlib.loads(
        (services / "請求書をリネーム.workflow" / "Contents" / "document.wflow").read_bytes()
    )
    script = wflow["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    script_path = work.parent / "qa.sh"
    script_path.write_text(script, encoding="utf-8")

    # macOS の osascript が無いので、ダイアログの応答を返すスタブを PATH に置く
    stub_dir = work.parent / "stub"
    stub_dir.mkdir(exist_ok=True)
    log = work.parent / "osascript.log"
    stub = stub_dir / "osascript"
    stub.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'if [[ "$*" == *"display dialog"* ]]; then '
        f'echo "button returned:{answer}"; fi\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)

    env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}
    result = subprocess.run(
        ["bash", str(script_path), *[str(t) for t in targets]],
        capture_output=True,
        env=env,
    )
    dialogs = log.read_text(encoding="utf-8") if log.exists() else ""
    return result, dialogs


def test_embedded_script_renames_selection_in_place(bundle_script_env):
    services, work = bundle_script_env
    a = write_pdf(work / "scan1.pdf", INVOICE_LINES)
    b = write_pdf(work / "scan2.pdf", NOTICE_LINES)

    result, dialogs = _run_embedded(services, work, [a, b])

    assert result.returncode == 0, result.stderr.decode()
    # 選択したファイルがその場で変わる（コピーではない）
    assert not a.exists()
    assert not b.exists()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()
    assert (work / "支払通知書 スタジオ コンテナ 御中.pdf").exists()
    assert "リネーム済み" not in [p.name for p in work.iterdir()]
    # 実行前に確認ダイアログを出している
    assert "display dialog" in dialogs
    assert "2 件をこの名前に変更します" in dialogs


def test_embedded_script_does_nothing_when_cancelled(bundle_script_env):
    services, work = bundle_script_env
    a = write_pdf(work / "scan1.pdf", INVOICE_LINES)

    result, _ = _run_embedded(services, work, [a], answer="キャンセル")

    assert result.returncode == 0, result.stderr.decode()
    assert a.exists()
    assert not (work / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_embedded_script_leaves_unreadable_files_alone(bundle_script_env):
    services, work = bundle_script_env
    good = write_pdf(work / "scan1.pdf", INVOICE_LINES)
    other = write_pdf(work / "quote.pdf", [(60, 90, "見積書", 20)])

    result, dialogs = _run_embedded(services, work, [good, other])

    assert result.returncode == 0, result.stderr.decode()
    assert other.exists()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()
    assert "1 件は読み取れないためそのままにします" in dialogs


def test_embedded_script_handles_a_folder_argument(bundle_script_env):
    services, work = bundle_script_env
    write_pdf(work / "scan1.pdf", INVOICE_LINES)

    result, _ = _run_embedded(services, work, [work])

    assert result.returncode == 0, result.stderr.decode()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_embedded_script_is_quiet_when_nothing_matches(bundle_script_env):
    services, work = bundle_script_env
    write_pdf(work / "quote.pdf", [(60, 90, "見積書", 20)])

    result, dialogs = _run_embedded(services, work, [work])

    assert result.returncode == 0, result.stderr.decode()
    # 確認ダイアログは出さず、通知だけで終わる
    assert "display dialog" not in dialogs
    assert "ありませんでした" in dialogs


@pytest.fixture
def bundle_script_env(tmp_path):
    services = tmp_path / "Services"
    cmd = Path(sys.executable).parent / "doc-namer"
    if not cmd.exists():
        pytest.skip("doc-namer コマンドが未インストール")
    qa.install(cmd, services, flush=False)
    work = tmp_path / "請求書"
    work.mkdir()
    return services, work

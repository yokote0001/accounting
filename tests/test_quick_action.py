"""クイックアクション（.workflow バンドル）の生成テスト。"""

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


def test_embedded_script_renames_a_folder(tmp_path, bundle_script_env):
    """バンドルに埋め込まれたシェルスクリプトを実際に動かす。"""
    services, work = bundle_script_env
    write_pdf(work / "a.pdf", INVOICE_LINES)
    write_pdf(work / "b.pdf", NOTICE_LINES)

    wflow = plistlib.loads(
        (services / "請求書をリネーム.workflow" / "Contents" / "document.wflow").read_bytes()
    )
    script = wflow["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    script_path = work.parent / "qa.sh"
    # macOS 専用の open / osascript はテスト環境に無いので無効化する
    script_path.write_text(
        script.replace("open \"$DEST\"", ":").replace("osascript", "true osascript"),
        encoding="utf-8",
    )

    result = subprocess.run(["bash", str(script_path), str(work)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    out = work / "リネーム済み"
    assert (out / "7月ご請求 合同会社がっく 御中.pdf").exists()
    assert (out / "支払通知書 スタジオ コンテナ 御中.pdf").exists()


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

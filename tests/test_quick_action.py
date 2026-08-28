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
    return qa.install(
        Path("/opt/doc-namer/bin/doc-namer"), services, flush=False, write_config=False
    )


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
    first = qa.install(Path("/old/doc-namer"), services, flush=False, write_config=False)
    (first / "Contents" / "stale.txt").write_text("x", encoding="utf-8")
    second = qa.install(Path("/new/doc-namer"), services, flush=False, write_config=False)
    assert not (second / "Contents" / "stale.txt").exists()
    wflow = plistlib.loads((second / "Contents" / "document.wflow").read_bytes())
    assert "/new/doc-namer" in wflow["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]


def _run_embedded(services, work, targets, answer="リネーム", home=None):
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
    if home is not None:
        env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(script_path), *[str(t) for t in targets]],
        capture_output=True,
        env=env,
    )
    dialogs = log.read_text(encoding="utf-8") if log.exists() else ""
    return result, dialogs


def test_embedded_script_renames_selection_in_place(bundle_script_env, fake_home):
    services, work = bundle_script_env
    a = write_pdf(work / "scan1.pdf", INVOICE_LINES)
    b = write_pdf(work / "scan2.pdf", NOTICE_LINES)

    result, dialogs = _run_embedded(services, work, [a, b], home=fake_home)

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


def test_embedded_script_does_nothing_when_cancelled(bundle_script_env, fake_home):
    services, work = bundle_script_env
    a = write_pdf(work / "scan1.pdf", INVOICE_LINES)

    result, _ = _run_embedded(services, work, [a], answer="キャンセル", home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    assert a.exists()
    assert not (work / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_embedded_script_leaves_unreadable_files_alone(bundle_script_env, fake_home):
    services, work = bundle_script_env
    good = write_pdf(work / "scan1.pdf", INVOICE_LINES)
    other = write_pdf(work / "quote.pdf", [(60, 90, "見積書", 20)])

    result, dialogs = _run_embedded(services, work, [good, other], home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    assert other.exists()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()
    assert "1 件は読み取れないためそのままにします" in dialogs


def test_embedded_script_handles_a_folder_argument(bundle_script_env, fake_home):
    services, work = bundle_script_env
    write_pdf(work / "scan1.pdf", INVOICE_LINES)

    result, _ = _run_embedded(services, work, [work], home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_unreadable_selection_says_it_could_not_read_them(bundle_script_env, fake_home):
    """読み取れなかった場合は件数を添えて伝える。"""
    services, work = bundle_script_env
    write_pdf(work / "quote.pdf", [(60, 90, "見積書", 20)])

    result, dialogs = _run_embedded(services, work, [work], home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    # 確認ダイアログは出さず、通知だけで終わる
    assert "display dialog" not in dialogs
    assert "1 件を請求書・支払通知書として読み取れませんでした" in dialogs


def test_selection_without_pdfs_says_so(bundle_script_env, fake_home):
    """PDF が1つも無い場合は、読み取り失敗とは別の案内を出す。"""
    services, work = bundle_script_env
    (work / "memo.txt").write_text("not a pdf", encoding="utf-8")

    result, dialogs = _run_embedded(services, work, [work], home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    assert "display dialog" not in dialogs
    assert "PDF が選ばれていません" in dialogs


@pytest.fixture
def doc_namer_cmd():
    cmd = Path(sys.executable).parent / "doc-namer"
    if not cmd.exists():
        pytest.skip("doc-namer コマンドが未インストール")
    return cmd


@pytest.fixture
def fake_home(tmp_path):
    """本物の $HOME を汚さないよう、テスト用のホームを用意する。"""
    home = tmp_path / "home"
    (home / ".config" / "doc-namer").mkdir(parents=True)
    return home


@pytest.fixture
def bundle_script_env(tmp_path, fake_home, doc_namer_cmd):
    services = tmp_path / "Services"
    qa.install(doc_namer_cmd, services, flush=False, write_config=False)
    (fake_home / ".config" / "doc-namer" / "command").write_text(
        str(doc_namer_cmd), encoding="utf-8"
    )
    work = tmp_path / "請求書"
    work.mkdir()
    return services, work


def test_install_survives_missing_pbs(tmp_path):
    """pbs が無い環境でも、バンドルの生成自体は成功する。"""
    services = tmp_path / "Services"
    bundle = qa.install(Path("/opt/doc-namer"), services, flush=True, write_config=False)
    assert (bundle / "Contents" / "document.wflow").is_file()


def test_service_uuid_is_shared_between_plists(bundle):
    info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
    wflow = plistlib.loads((bundle / "Contents" / "document.wflow").read_bytes())
    service_uuid = info["NSServices"][0]["NSUUID"]
    assert service_uuid
    assert wflow["workflowMetaData"]["serviceUUID"] == service_uuid


def test_info_plist_has_the_keys_finder_needs(bundle):
    service = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())["NSServices"][0]
    for key in ("NSUUID", "NSIconName", "NSBackgroundColorName"):
        assert key in service, key


def test_shipped_bundle_reads_command_from_config(tmp_path, fake_home, doc_namer_cmd):
    """配布用バンドル（パスが焼き込まれていない）でも設定ファイルから解決できる。"""
    services = tmp_path / "Services"
    qa.install(Path("/does/not/exist"), services, flush=False, write_config=False)
    (fake_home / ".config" / "doc-namer" / "command").write_text(
        str(doc_namer_cmd), encoding="utf-8"
    )
    work = tmp_path / "請求書"
    work.mkdir()
    write_pdf(work / "scan.pdf", INVOICE_LINES)

    result, _ = _run_embedded(services, work, [work], home=fake_home)

    assert result.returncode == 0, result.stderr.decode()
    assert (work / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_bundle_warns_when_setup_has_not_run(tmp_path, fake_home):
    """doc-namer が見つからないときは、黙って失敗せず案内を出す。"""
    services = tmp_path / "Services"
    qa.install(Path("/does/not/exist"), services, flush=False, write_config=False)
    work = tmp_path / "請求書"
    work.mkdir()
    (work / "dummy.pdf").write_bytes(b"%PDF-1.4\n")

    result, dialogs = _run_embedded(services, work, [work], home=fake_home)

    assert result.returncode == 1
    assert "セットアップが必要です" in dialogs


def test_install_writes_the_command_path(tmp_path, monkeypatch, doc_namer_cmd):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    qa.install(doc_namer_cmd, tmp_path / "Services", flush=False)
    conf = home / ".config" / "doc-namer" / "command"
    assert conf.read_text(encoding="utf-8") == str(doc_namer_cmd)

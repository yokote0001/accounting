"""生成した PDF を通した end-to-end テスト。"""

import pytest

from doc_namer.cli import main
from doc_namer.extract import extract

pymupdf = pytest.importorskip("pymupdf")

INVOICE_LINES = [
    (60, 90, "INVOICE 請求書", 20),
    (60, 150, "合同会社がっく 御中", 22),
    (60, 190, "件名：ABCmovieにつきまして", 11),
    (60, 215, "下記のとおりにご請求申し上げます。", 11),
    (60, 245, "ご請求金額 ￥11,550", 13),
    (60, 275, "お支払い期限：2026年8月31日", 11),
    (60, 400, "ABCmovie(プレミアBプラン)月額利用料 ￥10,500", 10),
    (60, 500, "ご請求日：2026年7月31日", 11),
]

NOTICE_LINES = [
    (60, 90, "PAYMENT NOTICE 支払通知書", 20),
    (60, 150, "スタジオ コンテナ 御中", 22),
    (60, 190, "件名：ご紹介手数料", 11),
    (60, 215, "下記の通り、お支払い申し上げます。", 11),
    (60, 245, "お支払額 ￥22,000", 13),
    (60, 275, "お支払い日：2026年9月30日", 11),
    (60, 400, "ご紹介手数料(株式会社EDIN様) ￥20,000", 10),
]


def write_pdf(path, lines):
    doc = pymupdf.open()
    page = doc.new_page()
    for x, y, text, size in lines:
        page.insert_text((x, y), text, fontname="japan", fontsize=size)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def invoice_pdf(tmp_path):
    return write_pdf(tmp_path / "scan001.pdf", INVOICE_LINES)


@pytest.fixture
def notice_pdf(tmp_path):
    return write_pdf(tmp_path / "scan002.pdf", NOTICE_LINES)


def test_extract_invoice(invoice_pdf):
    doc = extract(invoice_pdf)
    assert doc.doc_type.key == "invoice"
    assert doc.recipient == "合同会社がっく 御中"
    # 支払期限(8月)ではなく請求日(7月)を採る
    assert (doc.year, doc.month, doc.day) == (2026, 7, 31)


def test_extract_payment_notice(notice_pdf):
    doc = extract(notice_pdf)
    assert doc.doc_type.key == "payment_notice"
    assert doc.recipient == "スタジオ コンテナ 御中"
    assert (doc.year, doc.month, doc.day) == (2026, 9, 30)


def test_cli_copies_with_new_names(tmp_path, invoice_pdf, notice_pdf):
    out = tmp_path / "out"
    assert main([str(invoice_pdf), str(notice_pdf), "-o", str(out)]) == 0
    assert (out / "7月ご請求 合同会社がっく 御中.pdf").exists()
    assert (out / "9月お支払い スタジオ コンテナ 御中.pdf").exists()
    # コピーなので元ファイルは残る
    assert invoice_pdf.exists()


def test_cli_dry_run_writes_nothing(tmp_path, invoice_pdf, capsys):
    out = tmp_path / "out"
    assert main([str(invoice_pdf), "-o", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert "7月ご請求 合同会社がっく 御中.pdf" in capsys.readouterr().out


def test_cli_move_renames_in_place(tmp_path, invoice_pdf):
    assert main([str(invoice_pdf), "--move"]) == 0
    assert not invoice_pdf.exists()
    assert (invoice_pdf.parent / "7月ご請求 合同会社がっく 御中.pdf").exists()


def test_cli_accepts_a_folder(tmp_path, invoice_pdf, notice_pdf):
    out = tmp_path / "out"
    assert main([str(invoice_pdf.parent), "-o", str(out)]) == 0
    assert len(list(out.glob("*.pdf"))) == 2


def test_cli_avoids_overwriting(tmp_path, invoice_pdf):
    out = tmp_path / "out"
    main([str(invoice_pdf), "-o", str(out)])
    main([str(invoice_pdf), "-o", str(out)])
    assert (out / "7月ご請求 合同会社がっく 御中 (2).pdf").exists()


def test_cli_reports_unrecognised_pdf(tmp_path, capsys):
    other = write_pdf(tmp_path / "quote.pdf", [(60, 90, "見積書", 20)])
    out = tmp_path / "out"
    assert main([str(other), "-o", str(out)]) == 1
    assert "[NG]" in capsys.readouterr().err

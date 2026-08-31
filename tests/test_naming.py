from pathlib import Path

import pytest

from doc_namer.config import DEFAULT_CONFIG, load_config
from doc_namer.extract import ExtractedDoc
from doc_namer.naming import (
    build_fields,
    build_filename,
    missing_fields,
    sanitize,
    template_fields,
    unique_path,
)


def make_doc(type_key, recipient, year=2026, month=7, day=31):
    return ExtractedDoc(
        path=Path("original.pdf"),
        doc_type=DEFAULT_CONFIG.get(type_key),
        recipient=recipient,
        year=year,
        month=month,
        day=day,
        date_label="ご請求日",
        text="",
    )


def test_invoice_filename_matches_requested_format():
    doc = make_doc("invoice", "合同会社がっく 御中", month=7)
    assert build_filename(doc, DEFAULT_CONFIG) == "7月ご請求 合同会社がっく 御中.pdf"


def test_payment_notice_filename_starts_with_the_month():
    doc = make_doc("payment_notice", "スタジオ コンテナ 御中", month=9)
    assert build_filename(doc, DEFAULT_CONFIG) == "9月支払通知書 スタジオ コンテナ 御中.pdf"


def test_payment_notice_needs_a_date_now():
    # 月を使うようになったので、日付が読めないものは出力できない
    doc = ExtractedDoc(
        path=Path("x.pdf"),
        doc_type=DEFAULT_CONFIG.get("payment_notice"),
        recipient="スタジオ コンテナ 御中",
        year=None,
        month=None,
        day=None,
        date_label=None,
        text="",
    )
    assert missing_fields(doc, DEFAULT_CONFIG) == ["日付"]


def test_invoice_still_needs_a_date():
    doc = make_doc("invoice", "合同会社がっく 御中", year=None, month=None, day=None)
    assert missing_fields(doc, DEFAULT_CONFIG) == ["日付"]
    with pytest.raises(ValueError, match="日付"):
        build_filename(doc, DEFAULT_CONFIG)


def test_missing_recipient_is_reported():
    doc = make_doc("payment_notice", None)
    assert missing_fields(doc, DEFAULT_CONFIG) == ["宛名"]


def test_template_fields_ignores_format_spec():
    assert template_fields("{year}年{month2:>3}月 {recipient}") == [
        "year",
        "month2",
        "recipient",
    ]


def test_unknown_placeholder_is_rejected(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[document_types.invoice]\ndetect = ["請求書"]\ntemplate = "{nope} {recipient}"\n',
        encoding="utf-8",
    )
    config = load_config(config_file)
    doc = ExtractedDoc(
        Path("x.pdf"), config.get("invoice"), "A 御中", 2026, 7, 31, "ご請求日", ""
    )
    with pytest.raises(ValueError, match="nope"):
        build_filename(doc, config)


def test_month_is_not_zero_padded():
    doc = make_doc("invoice", "株式会社エー 御中", month=1)
    assert build_filename(doc, DEFAULT_CONFIG).startswith("1月ご請求 ")


def test_build_fields_splits_honorific():
    fields = build_fields(make_doc("invoice", "合同会社がっく 御中"), DEFAULT_CONFIG)
    assert fields["recipient_name"] == "合同会社がっく"
    assert fields["honorific"] == "御中"
    assert fields["month2"] == "07"
    assert fields["ym"] == "202607"


def test_build_filename_requires_doc_type():
    doc = ExtractedDoc(Path("a.pdf"), None, "株式会社エー 御中", 2026, 7, 31, None, "")
    assert missing_fields(doc, DEFAULT_CONFIG) == ["書類種別"]
    with pytest.raises(ValueError):
        build_filename(doc, DEFAULT_CONFIG)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("7月ご請求 A/B社 御中", "7月ご請求 A_B社 御中"),
        ("株式会社  スペース   御中", "株式会社 スペース 御中"),
        ("末尾ドット. ", "末尾ドット"),
        ('危険:"文字"', "危険__文字_"),
    ],
)
def test_sanitize(raw, expected):
    assert sanitize(raw) == expected


def test_unique_path_avoids_collision(tmp_path):
    (tmp_path / "7月ご請求 A社 御中.pdf").touch()
    got = unique_path(tmp_path, "7月ご請求 A社 御中.pdf")
    assert got.name == "7月ご請求 A社 御中 (2).pdf"


def test_custom_template_from_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[document_types.invoice]
label = "請求書"
detect = ["請求書"]
date_labels = ["ご請求日"]
template = "{ym}_{label}_{recipient_name}"
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    doc = ExtractedDoc(
        Path("x.pdf"), config.get("invoice"), "合同会社がっく 御中", 2026, 7, 31, "ご請求日", ""
    )
    assert build_filename(doc, config) == "202607_請求書_合同会社がっく.pdf"


def test_load_config_rejects_missing_template(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[document_types.invoice]\nlabel = "請求書"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_file)


def test_extension_is_lowercased():
    doc = make_doc("invoice", "合同会社がっく 御中", month=7)
    doc = ExtractedDoc(
        path=Path("SCAN001.PDF"),
        doc_type=doc.doc_type,
        recipient=doc.recipient,
        year=doc.year,
        month=doc.month,
        day=doc.day,
        date_label=doc.date_label,
        text="",
    )
    assert build_filename(doc, DEFAULT_CONFIG).endswith(".pdf")

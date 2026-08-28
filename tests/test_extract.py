from doc_namer.config import DEFAULT_CONFIG
from doc_namer.extract import TextLine, detect_doc_type, find_date, find_recipient, normalize


def line(text, size=10.0, y=0.0):
    return TextLine(text=text, size=size, page=0, y=y, x=0.0)


def test_normalize_collapses_full_width_space():
    assert normalize("合同会社がっく　御中") == "合同会社がっく 御中"


def test_detects_invoice():
    rule = detect_doc_type("INVOICE\n請求書\nご請求日：2026年7月31日", DEFAULT_CONFIG)
    assert rule is not None and rule.key == "invoice"


def test_detects_payment_notice():
    rule = detect_doc_type("PAYMENT NOTICE\n支払通知書\nお支払い日：2026年9月30日", DEFAULT_CONFIG)
    assert rule is not None and rule.key == "payment_notice"


def test_payment_notice_wins_when_both_words_appear():
    # 支払通知書に「ご請求」が混ざっても請求書と取り違えない
    text = "支払通知書\nご請求金額\nお支払い日：2026年9月30日"
    rule = detect_doc_type(text, DEFAULT_CONFIG)
    assert rule is not None and rule.key == "payment_notice"


def test_unknown_doc_type_is_none():
    assert detect_doc_type("見積書\n御見積金額", DEFAULT_CONFIG) is None


def test_recipient_prefers_largest_font():
    lines = [
        line("ご紹介手数料(株式会社EDIN様)", size=9.0, y=300),
        line("スタジオ コンテナ 御中", size=22.0, y=100),
    ]
    assert find_recipient(lines, DEFAULT_CONFIG) == "スタジオ コンテナ 御中"


def test_recipient_ignores_honorific_inside_line():
    # 行末が敬称でなければ宛名候補にしない
    lines = [line("ご紹介手数料(株式会社EDIN様)につきまして", size=30.0)]
    assert find_recipient(lines, DEFAULT_CONFIG) is None


def test_recipient_uses_topmost_line_on_size_tie():
    lines = [
        line("株式会社ビー 様", size=20.0, y=400),
        line("株式会社エー 御中", size=20.0, y=100),
    ]
    assert find_recipient(lines, DEFAULT_CONFIG) == "株式会社エー 御中"


def test_recipient_none_when_only_honorific():
    assert find_recipient([line("御中", size=20.0)], DEFAULT_CONFIG) is None


def test_find_date_uses_first_matching_label():
    text = "お支払い期限：2026年9月30日\nご請求日：2026年8月31日"
    year, month, day, label = find_date(text, ("ご請求日", "お支払い期限"))
    assert (year, month, day, label) == (2026, 8, 31, "ご請求日")


def test_find_date_falls_back_to_next_label():
    text = "お支払い期限：2026年9月30日"
    year, month, day, label = find_date(text, ("ご請求日", "お支払い期限"))
    assert (year, month, day, label) == (2026, 9, 30, "お支払い期限")


def test_find_date_tolerates_spacing():
    text = "ご請求日 ： 2026 年 7 月 31 日"
    assert find_date(text, ("ご請求日",))[:3] == (2026, 7, 31)


def test_find_date_returns_none_when_absent():
    assert find_date("金額のみ", ("ご請求日",)) == (None, None, None, None)

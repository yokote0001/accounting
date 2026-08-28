"""PDF から書類種別・宛名・日付を取り出す。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Config, DocTypeRule, DEFAULT_CONFIG

# 「2026年8月31日」「2026 年 8 月 31 日」など
_DATE_RE = r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
# ラベルと値の間に入りうる区切り
_SEP_RE = r"[\s　:：]*"


@dataclass(frozen=True)
class TextLine:
    text: str
    size: float
    page: int
    y: float
    x: float


@dataclass(frozen=True)
class ExtractedDoc:
    path: Path
    doc_type: DocTypeRule | None
    recipient: str | None
    year: int | None
    month: int | None
    day: int | None
    date_label: str | None
    text: str

    # 何が揃っていれば足りるかは命名テンプレート次第なので、
    # 判定は naming.missing_fields() が持つ。


def read_lines(path: Path | str) -> list[TextLine]:
    """PDF の各行を、フォントサイズ付きで読み出す。"""
    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise RuntimeError(
            "pymupdf が必要です。`pip install -r requirements.txt` を実行してください。"
        ) from exc

    lines: list[TextLine] = []
    with pymupdf.open(path) as doc:
        for page_no, page in enumerate(doc):
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    text = "".join(span.get("text", "") for span in spans).strip()
                    if not text:
                        continue
                    size = max((span.get("size", 0.0) for span in spans), default=0.0)
                    bbox = line.get("bbox", (0, 0, 0, 0))
                    lines.append(TextLine(text, size, page_no, bbox[1], bbox[0]))
    return lines


def normalize(text: str) -> str:
    """全角空白などを均して照合しやすくする。"""
    text = text.replace("　", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def detect_doc_type(text: str, config: Config = DEFAULT_CONFIG) -> DocTypeRule | None:
    """本文から書類種別を判定する。priority の小さい順に照合。"""
    haystack = text.upper()
    for rule in config.ordered_types():
        for needle in rule.detect:
            if needle.upper() in haystack:
                return rule
    return None


def find_recipient(lines: list[TextLine], config: Config = DEFAULT_CONFIG) -> str | None:
    """「御中」「様」で終わる行のうち、いちばん大きな文字のものを宛名とみなす。

    明細行（例: ご紹介手数料(株式会社EDIN様)）を拾わないよう、敬称で終わる行だけを
    候補にし、同点なら上にあるものを優先する。
    """
    honorifics = sorted(config.honorifics, key=len, reverse=True)
    candidates: list[tuple[float, int, float, str]] = []
    for line in lines:
        norm = normalize(line.text)
        for honorific in honorifics:
            if norm.endswith(honorific):
                body = norm[: -len(honorific)].strip()
                if not body:
                    continue
                candidates.append((-line.size, line.page, line.y, f"{body} {honorific}"))
                break
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][3]


def find_date(
    text: str, labels: tuple[str, ...]
) -> tuple[int | None, int | None, int | None, str | None]:
    """日付ラベルを順に探し、最初に見つかった年月日を返す。"""
    for label in labels:
        pattern = re.escape(label) + _SEP_RE + _DATE_RE
        match = re.search(pattern, text)
        if match:
            return (
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
                label,
            )
    return None, None, None, None


def extract(path: Path | str, config: Config = DEFAULT_CONFIG) -> ExtractedDoc:
    """PDF 1 件からファイル名に必要な情報を取り出す。"""
    path = Path(path)
    lines = read_lines(path)
    # 照合用の本文。半角/全角ゆれを NFKC で吸収する
    text = unicodedata.normalize("NFKC", "\n".join(normalize(line.text) for line in lines))

    doc_type = detect_doc_type(text, config)
    recipient = find_recipient(lines, config)
    labels = doc_type.date_labels if doc_type else ()
    year, month, day, date_label = find_date(text, tuple(unicodedata.normalize("NFKC", label) for label in labels))

    return ExtractedDoc(
        path=path,
        doc_type=doc_type,
        recipient=recipient,
        year=year,
        month=month,
        day=day,
        date_label=date_label,
        text=text,
    )

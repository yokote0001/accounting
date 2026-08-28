"""抽出結果からファイル名を組み立てる。"""

from __future__ import annotations

import re
from pathlib import Path
from string import Formatter

from .config import Config, DEFAULT_CONFIG
from .extract import ExtractedDoc

# ファイル名に使えない / 使うと事故りやすい文字
_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# テンプレート変数 -> 足りないときに出すラベル
_FIELD_LABELS = {
    "recipient": "宛名",
    "recipient_name": "宛名",
    "honorific": "宛名",
    "year": "日付",
    "yy": "日付",
    "month": "日付",
    "month2": "日付",
    "day": "日付",
    "day2": "日付",
    "ym": "日付",
    "label": "書類種別",
    "type": "書類種別",
}


def sanitize(name: str, replacement: str = "_") -> str:
    """OS でファイル名にできる形に整える（日本語はそのまま残す）。"""
    name = _FORBIDDEN_RE.sub(replacement, name)
    name = re.sub(r"\s+", " ", name).strip()
    # 末尾の . と空白は Windows で落ちるので削る
    name = name.rstrip(". ")
    return name or "untitled"


def build_fields(doc: ExtractedDoc, config: Config = DEFAULT_CONFIG) -> dict[str, object]:
    """テンプレートに渡す変数を作る。"""
    recipient = doc.recipient or ""
    honorific = ""
    for candidate in sorted(config.honorifics, key=len, reverse=True):
        if recipient.endswith(candidate):
            honorific = candidate
            break
    recipient_name = recipient[: len(recipient) - len(honorific)].strip() if honorific else recipient

    return {
        "recipient": recipient,
        "recipient_name": recipient_name,
        "honorific": honorific,
        "year": doc.year if doc.year is not None else "",
        "yy": f"{doc.year % 100:02d}" if doc.year is not None else "",
        "month": doc.month if doc.month is not None else "",
        "month2": f"{doc.month:02d}" if doc.month is not None else "",
        "day": doc.day if doc.day is not None else "",
        "day2": f"{doc.day:02d}" if doc.day is not None else "",
        "ym": f"{doc.year}{doc.month:02d}" if doc.year and doc.month else "",
        "label": doc.doc_type.label if doc.doc_type else "",
        "type": doc.doc_type.key if doc.doc_type else "",
    }


def template_fields(template: str) -> list[str]:
    """テンプレートが使っている変数名を返す。`{month:02d}` の書式指定は除く。"""
    names = []
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        key = field_name.split(".")[0].split("[")[0]
        if key not in names:
            names.append(key)
    return names


def missing_fields(doc: ExtractedDoc, config: Config = DEFAULT_CONFIG) -> list[str]:
    """テンプレートが必要とする情報のうち、読み取れなかったものを返す。

    必要な情報はテンプレート次第。たとえば支払通知書のテンプレートが
    `{label} {recipient}` なら、日付が読めなくても出力できる。
    """
    if doc.doc_type is None:
        return ["書類種別"]
    fields = build_fields(doc, config)
    missing: list[str] = []
    for key in template_fields(doc.doc_type.template):
        if key not in fields:
            raise ValueError(
                f"{doc.doc_type.key}: テンプレートの {{{key}}} は使えない変数です"
            )
        if fields[key] in ("", None):
            label = _FIELD_LABELS.get(key, key)
            if label not in missing:
                missing.append(label)
    return missing


def build_filename(doc: ExtractedDoc, config: Config = DEFAULT_CONFIG) -> str:
    """拡張子込みのファイル名を返す。"""
    missing = missing_fields(doc, config)
    if missing:
        raise ValueError(f"{doc.path.name}: {' / '.join(missing)} を特定できませんでした")
    stem = doc.doc_type.template.format(**build_fields(doc, config))
    return sanitize(stem, config.replacement) + doc.path.suffix


def unique_path(directory: Path, filename: str) -> Path:
    """同名ファイルがあれば ` (2)` `(3)` … を足して衝突を避ける。"""
    target = directory / filename
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for n in range(2, 1000):
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"{filename}: 空いているファイル名が見つかりません")

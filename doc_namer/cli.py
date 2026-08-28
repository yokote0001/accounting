"""コマンドラインから請求書 / 支払通知書 PDF をリネーム出力する。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .config import load_config
from .extract import extract
from .naming import build_filename, missing_fields, unique_path


def collect_pdfs(inputs: list[str], recursive: bool) -> list[Path]:
    """引数のファイル / フォルダから PDF を集める。"""
    found: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            found.extend(sorted(p for p in path.glob(pattern) if p.is_file()))
        elif path.is_file():
            found.append(path)
        else:
            print(f"見つかりません: {path}", file=sys.stderr)
    # 重複を除きつつ順番は保つ
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in found:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-namer",
        description="請求書 / 支払通知書 PDF の中身を読んで「7月ご請求 合同会社がっく 御中.pdf」のような名前で出力します。",
    )
    parser.add_argument("inputs", nargs="+", help="PDF ファイル、または PDF の入ったフォルダ")
    parser.add_argument(
        "-o", "--out-dir", default="out", help="出力先フォルダ（既定: out）"
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="コピーではなく元ファイルをその場でリネームする",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="実際には書き込まず、結果だけ表示する"
    )
    parser.add_argument("-c", "--config", help="設定 TOML のパス（既定: config.toml）")
    parser.add_argument(
        "--json", action="store_true", help="抽出結果を JSON で出力する"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="フォルダを再帰的に探す"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="同名ファイルがあれば上書きする（既定は ` (2)` を付けて回避）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)

    pdfs = collect_pdfs(args.inputs, args.recursive)
    if not pdfs:
        print("処理対象の PDF がありません。", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    if not args.dry_run and not args.move:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    failures = 0
    for pdf in pdfs:
        try:
            doc = extract(pdf, config)
        except Exception as exc:  # 壊れた PDF などは 1 件で止めずに続ける
            failures += 1
            print(f"[NG] {pdf.name}: 読み取りに失敗しました ({exc})", file=sys.stderr)
            continue

        missing = missing_fields(doc, config)
        if missing:
            failures += 1
            print(
                f"[NG] {pdf.name}: {' / '.join(missing)} を特定できませんでした",
                file=sys.stderr,
            )
            continue

        filename = build_filename(doc, config)
        target_dir = pdf.parent if args.move else out_dir
        if args.overwrite or args.dry_run:
            target = target_dir / filename
        else:
            target = unique_path(target_dir, filename)

        record = {
            "source": str(pdf),
            "target": str(target),
            "doc_type": doc.doc_type.key if doc.doc_type else None,
            "label": doc.doc_type.label if doc.doc_type else None,
            "recipient": doc.recipient,
            "date_label": doc.date_label,
            "date": f"{doc.year}-{doc.month:02d}-{doc.day:02d}"
            if doc.year and doc.month and doc.day
            else None,
        }
        results.append(record)

        if args.dry_run:
            print(f"[DRY] {pdf.name}  ->  {target}")
            continue

        if args.move:
            if target.resolve() == pdf.resolve():
                print(f"[--] {pdf.name}（すでに正しい名前です）")
                continue
            pdf.replace(target)
        else:
            shutil.copy2(pdf, target)
        print(f"[OK] {pdf.name}  ->  {target}")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

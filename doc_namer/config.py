"""書類種別ごとの判定ルールと命名テンプレートの設定。

設定は TOML で上書きできる。config.toml を参照。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# 設定ファイルを探す順番。先に見つかったものを使う。
#   1. ~/.config/doc-namer/config.toml   （どこにインストールしても効く個人設定）
#   2. リポジトリ直下の config.toml       （editable インストール時はこれが本体）
USER_CONFIG_PATH = Path.home() / ".config" / "doc-namer" / "config.toml"
REPO_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def find_config() -> Path | None:
    """既定の探索順で設定ファイルを探す。見つからなければ None。"""
    for candidate in (USER_CONFIG_PATH, REPO_CONFIG_PATH):
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class DocTypeRule:
    """1 つの書類種別（請求書 / 支払通知書 など）のルール。"""

    key: str
    label: str
    # 本文にこの語が含まれていればその種別と判定する
    detect: tuple[str, ...] = ()
    # 「何月」を決めるために順番に探す日付ラベル
    date_labels: tuple[str, ...] = ()
    # ファイル名テンプレート（拡張子は付けない）
    template: str = "{month}月 {recipient}"
    # 判定の優先順位。小さいほど先に判定される
    priority: int = 100


@dataclass(frozen=True)
class Config:
    doc_types: tuple[DocTypeRule, ...]
    # 宛名として認めるサフィックス（長い順に照合する）
    honorifics: tuple[str, ...] = ("御中", "様")
    # ファイル名に使えない文字の置換先
    replacement: str = "_"

    def ordered_types(self) -> list[DocTypeRule]:
        return sorted(self.doc_types, key=lambda r: (r.priority, r.key))

    def get(self, key: str) -> DocTypeRule | None:
        for rule in self.doc_types:
            if rule.key == key:
                return rule
        return None


DEFAULT_DOC_TYPES: tuple[DocTypeRule, ...] = (
    DocTypeRule(
        key="payment_notice",
        label="支払通知書",
        detect=("支払通知書", "PAYMENT NOTICE"),
        date_labels=("お支払い日", "お支払日", "支払日", "ご請求日"),
        # 支払通知書は月を入れない（日付が読めなくても出力できる）
        template="{label} {recipient}",
        # 「請求」より先に判定する（支払通知書に請求の語が混ざっても取り違えないため）
        priority=10,
    ),
    DocTypeRule(
        key="invoice",
        label="請求書",
        detect=("請求書", "INVOICE", "ご請求金額", "ご請求日"),
        date_labels=("ご請求日", "請求日", "発行日", "お支払い期限"),
        template="{month}月ご請求 {recipient}",
        priority=20,
    ),
)

DEFAULT_CONFIG = Config(doc_types=DEFAULT_DOC_TYPES)


def load_config(path: Path | str | None = None) -> Config:
    """TOML を読み込んで Config を返す。ファイルが無ければ既定値。

    TOML に書かれた種別だけが有効になる（既定値との併合はしない）ので、
    設定ファイルを置くときは使う種別をすべて記述すること。
    """
    if path is None:
        found = find_config()
        if found is None:
            return DEFAULT_CONFIG
        path = found
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    types_raw = raw.get("document_types") or {}
    if not types_raw:
        raise ValueError(f"{path}: [document_types] が空です")

    rules = []
    for key, body in types_raw.items():
        if "template" not in body:
            raise ValueError(f"{path}: document_types.{key} に template がありません")
        rules.append(
            DocTypeRule(
                key=key,
                label=body.get("label", key),
                detect=tuple(body.get("detect", ())),
                date_labels=tuple(body.get("date_labels", ())),
                template=body["template"],
                priority=int(body.get("priority", 100)),
            )
        )

    general = raw.get("general") or {}
    return Config(
        doc_types=tuple(rules),
        honorifics=tuple(general.get("honorifics", DEFAULT_CONFIG.honorifics)),
        replacement=general.get("replacement", DEFAULT_CONFIG.replacement),
    )

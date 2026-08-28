# doc_namer — 請求書 / 支払通知書 PDF の自動リネーム

Fairy effect の雛形で作った PDF を読み取り、
**「7月ご請求 合同会社がっく 御中.pdf」** のようなファイル名で出力し直します。
請求書（INVOICE）と支払通知書（PAYMENT NOTICE）の両方に同じ仕組みで対応します。

| 書類 | 既定のファイル名 |
| --- | --- |
| 請求書 | `7月ご請求 合同会社がっく 御中.pdf` |
| 支払通知書 | `9月お支払い スタジオ コンテナ 御中.pdf` |

## 使い方

```bash
pip install -r requirements.txt

# まず結果だけ確認（何も書き込まない）
python -m doc_namer ~/Desktop/請求書 --dry-run

# out/ フォルダに新しい名前でコピー
python -m doc_namer ~/Desktop/請求書

# 元ファイルをその場でリネーム
python -m doc_namer ~/Desktop/請求書 --move
```

ファイルを直接指定することもできます。

```bash
python -m doc_namer invoice1.pdf invoice2.pdf -o 出力先
```

### オプション

| オプション | 説明 |
| --- | --- |
| `-o, --out-dir` | 出力先フォルダ（既定: `out`） |
| `--move` | コピーせず元ファイルをその場でリネーム |
| `-n, --dry-run` | 書き込まずに結果だけ表示 |
| `-r, --recursive` | フォルダを再帰的に探す |
| `--overwrite` | 同名ファイルを上書き（既定は ` (2)` を付けて回避） |
| `--json` | 読み取った宛名・日付などを JSON で出力 |
| `-c, --config` | 設定 TOML のパス（既定: `config.toml`） |

## 何を読み取っているか

1. **書類種別** — 本文に「支払通知書 / PAYMENT NOTICE」があれば支払通知書、
   「請求書 / INVOICE」があれば請求書。支払通知書を先に判定するので、
   本文に「ご請求」の語が混ざっていても取り違えません。
2. **宛名** — 「御中」「様」で終わる行のうち、**いちばん文字が大きい行**。
   明細の `ご紹介手数料(株式会社EDIN様)` のような行末が敬称でないものは拾いません。
3. **月** — 書類種別ごとに決めた日付ラベルを上から順に探します。
   - 請求書: `ご請求日` → `請求日` → `発行日` → `お支払い期限`
   - 支払通知書: `お支払い日` → `お支払日` → `支払日` → `ご請求日`

   請求書は**お支払い期限ではなく「ご請求日」の月**を使います。
   例）ご請求日 2026年7月31日 / お支払い期限 2026年8月31日 → `7月ご請求`

読み取れなかった PDF はスキップして、理由を標準エラーに出します
（処理はそこで止まりません）。

## 名前の形を変えたいとき

`config.toml` の `template` を書き換えるだけです。

```toml
[document_types.invoice]
template = "{month}月ご請求 {recipient}"       # 7月ご請求 合同会社がっく 御中
# template = "{ym}_請求書_{recipient_name}"   # 202607_請求書_合同会社がっく
# template = "{year}年{month2}月請求 {recipient}"
```

使える変数:

| 変数 | 例 |
| --- | --- |
| `{recipient}` | `合同会社がっく 御中` |
| `{recipient_name}` | `合同会社がっく` |
| `{honorific}` | `御中` |
| `{month}` / `{month2}` | `7` / `07` |
| `{year}` / `{yy}` | `2026` / `26` |
| `{day}` / `{day2}` | `31` / `31` |
| `{ym}` | `202607` |
| `{label}` / `{type}` | `請求書` / `invoice` |

見積書など新しい書類を増やすときは `[document_types.〇〇]` を足して、
`detect` / `date_labels` / `template` / `priority` を書きます。

## テスト

```bash
pip install pytest
python -m pytest tests -q
```

PDF を使う end-to-end テストも含め、テスト用の PDF はその場で生成するので、
実際の請求書をリポジトリに置く必要はありません。

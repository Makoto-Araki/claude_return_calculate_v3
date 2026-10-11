# CLAUDE.md

このファイルは、このリポジトリで作業するClaude Code (claude.ai/code) に向けたガイダンスを提供する。

## プロジェクト概要

2つの正の整数を受け取り、四則演算を行うシンプルな計算APIサーバー。

## エンドポイント

- `add`: 加算
- `subtract`: 減算
- `multiply`: 乗算
- `divide`: 除算

## 仕様

- 引数は正の整数2つ（例: `a`, `b`）
- divide で b=0 は正の整数でないため 422 エラーを返す
- divide の結果が小数の場合は小数点第2位を四捨五入して小数点以下を1桁にする
- divide の四捨五入は ROUND_HALF_UP（`round()` の偶数丸めではなく、5 を切り上げる）と同じ結果になる丸めにする。`decimal` の使用は必須としない（`Decimal` の既定の精度では、商の整数部が 28 桁を超えると 500 になるため、整数演算で丸めてよい）
- divide で割り切れる場合は整数で返す（float の範囲を超えていても、int のまま 200 で返す）
- divide で割り切れない商を丸めた値が float の範囲（約 1.8×10^308）を超える場合は 422 エラーを返す（float にすると `inf` になり、JSON にできず 500 になるため）。422 は FastAPI 標準の検証エラー形式（`detail` が配列）にする
- divide で商が極端に小さく、丸めると 0.0 になる場合は、200 で float の `0.0` を返す
- subtract で結果が負数の場合は問題なし
- 入力が正の整数でない場合は 422 エラーを返す
- 入力が 4300 桁を超える場合は 422 エラーを返す（Python の整数の文字列変換の上限。超えると 500 になるため）
- multiply で積が 4300 桁を超える場合は 422 エラーを返す（ちょうど 4300 桁は 200）。422 は FastAPI 標準の検証エラー形式（`detail` が配列）にする
- 計算結果は整数は int、小数は float で返す
- APIサーバーへのプロトコルは HTTP を使用する

## 引数の渡し方

| 演算名    | 引数の渡し方             |
| -------- | ----------------------- |
| add      | `GET /add?a=1&b=2`      |
| subtract | `GET /subtract?a=1&b=2` |
| multiply | `GET /multiply?a=1&b=2` |
| divide   | `GET /divide?a=1&b=2`   |

## HTTPメソッドの正常時・異常時のレスポンス形式

```text
{
    "result": 3 # 正常時は結果のみ返す
}

{
    "detail": [] # 422。detail は FastAPI 標準の検証エラー配列
}

{
    "detail": "Invalid API key" # 401。detail は文字列
}

{
    "detail": "Rate limit exceeded" # 429。detail は文字列。Retry-After ヘッダーを付ける
}
```

## 認証とレート制限

4つの計算エンドポイント（`add` / `subtract` / `multiply` / `divide`）すべてに、APIキー認証とユーザーごとのレート制限をかける。レート制限が成り立つかを確かめる実験である。

### 処理順序

1. 認証（失敗なら 401）
2. レート制限（超過なら 429）
3. 入力検証（失敗なら 422）

- 認証に成功したリクエストは、422 になる場合も 1 回として数える。認証に失敗したリクエストは数えない。
- 認証とレート制限は、FastAPI の依存関係（`Depends`）として実装する。エンドポイント本体のコードは変えない。
- 未認証で不正な入力（例: `a=0`）を送ったら 401、レート制限の超過中に不正な入力を送ったら 429 になる（422 にならない）。

### 認証

- 認証情報は、リクエストヘッダー `X-API-Key` で渡す。
- キーは設定ファイルのユーザーと 1 対 1 で対応し、キーからユーザーを特定する。
- ヘッダーがない場合も、キーが一致しない場合も、同じ 401 を返す（本文は `{"detail": "Invalid API key"}`）。両者を区別しない。
- キーの比較は、タイミング攻撃を避けるため `hmac.compare_digest` を使う。`str` のまま比べると、ASCII 以外の文字で `TypeError`（500）になるため、バイト列（UTF-8）にして比べる。ASCII 以外の文字を含むキーは、500 ではなく 401 を返す。
- ヘッダー値の前後の空白は取り除かない。前後に空白のあるキーは、一致しないので 401 を返す。空のキーも 401 を返す。
- キーを、ログ、レスポンス本文、エラーメッセージに出さない。
- API の構成が認証なしで見えないよう、`/docs`・`/redoc`・`/openapi.json` は無効にする（認証なしでも認証ありでも 404）。動作の確認には `curl` などを使う。

### ユーザーとキーの管理

- 設定ファイルは TOML 形式で、`config/users.toml` に置く。環境変数 `USERS_CONFIG_PATH` で場所を上書きできる。
- 形式は次のとおり。`[[users]]` は 1 件以上で、`name` と `api_key` は空でない文字列。どちらもユーザー間で重複させない。

```toml
[[users]]
name = "alice"
api_key = "dummy-key-for-alice"
```

- `api_key` は ASCII の文字列にする。ASCII 以外の文字を含むキーは、HTTP ヘッダーの復号の都合で、設定しても一致しない（認証できない）。雛形のコメントにもそう書く。
- 設定ファイルが見つからない、UTF-8 として読めない、形式が不正、`[[users]]` が 0 件、`name` または `api_key` が空・文字列でない・重複している場合は、起動時にエラーで止める（リクエスト時に 500 にしない）。エラーは `UsersConfigError` に統一し、メッセージにキーの値やファイルの内容を含めない。
- 実際のキーを含む `config/users.toml` は Git にコミットしない（`.gitignore` に入れる）。リポジトリには、キーを含まない雛形 `config/users.example.toml` だけを置く。
- テストは、実際の設定ファイルを読まない。ダミーのキーを使った設定を、テストごとに注入する。

### レート制限

- 方式は固定ウィンドウで、1 ユーザーにつき 1 分あたり 60 回まで。
- ウィンドウは、時計の分の区切り（UNIX 時間を 60 で割った商）で決める。
- 1 ウィンドウ内の 61 回目以降のリクエストは、ウィンドウが終わるまで 429 を返す。制限は一時的なもので、次のウィンドウで自動的に解除される。
- 429 には、ウィンドウが終わるまでの残り秒数を `Retry-After` ヘッダーに付ける（切り上げた整数で、最小 1）。
- すべてのエンドポイントを 1 回として数える（重みは付けない）。
- カウントはユーザーごとに独立させ、他のユーザーに影響しない。
- カウントはプロセス内のメモリに持つ。再起動で消え、複数プロセス間では共有しない。古いウィンドウのカウントは残さない。
- カウントの更新は、同時アクセスでずれないよう、排他制御する。
- 現在時刻は差し替えられる設計にする。テストでは時計を進めて検証し、実時間を待たない。
- テストは、カウントの状態を各テストの前にリセットする。

### 範囲外

- TLS は使わず、HTTP のままにする（実験のため。キーは平文で流れる）。
- 429 以外の制限（ブロックなど）、ユーザーごとの上限の違い、エンドポイントごとの重み、カウントの永続化は扱わない。

## 開発環境

- APIサーバーは Dev Container 内で起動（起動コマンドはコンテナ内で実行）
- Dockerfile は Dev Container のイメージ定義

## 開発フロー

- TDD で進める（テストエージェント → 実装エージェント → レビューエージェント）
- エンドポイントごとの進め方は `/tdd <エンドポイント名>` スキルに定める（`.claude/skills/tdd/SKILL.md`）
- エンドポイントではない部品（認証、レート制限のカウンターなど）の進め方は `/tdd-component <部品名>` スキルに定める（`.claude/skills/tdd-component/SKILL.md`）。エージェントと周回のルールは `/tdd` と同じ
- 各エージェントの定義は `.claude/agents/` に置く
- 依存パッケージを追加・更新した場合（`pyproject.toml` や `uv.lock` を変更した場合）は、`pip-audit` を実行して既知の脆弱性がないことを確認する。脆弱性が見つかった場合は、作業を止めて報告する
- 新しい脆弱性の公開により、コードを変えなくても CI の `pip-audit` が失敗することがある。その場合は、該当パッケージの更新を別の作業として扱う
- レビューで承認が出るまでを最大3周とし、3周で承認されない場合、または同じ指摘が2周続いた場合は、作業を止めて報告する
- 報告には、エンドポイント名、各周の指摘の要約、未解決の指摘、考えられる原因を含める

## Git 運用

- 開発ブランチは `main` から切る。名前は英小文字とハイフンで付ける（例: `add-endpoint-divide`）
- コミットメッセージ、PR のタイトルと本文は日本語で書く
- PR は GitHub 上でスカッシュマージする。マージと GitHub 上のブランチ削除はユーザーが行う
- PR と、マージ後の `main` で、GitHub Actions の CI（lint・フォーマット差分チェック・型チェック・テスト・依存パッケージの脆弱性監査）が走る。CI の定義は `.github/workflows/ci.yml`。CI の成功をマージの必須条件にするブランチ保護は、ユーザーが GitHub の設定で行う
- コミット、プッシュ、PR 作成は、ユーザーが明示的に指示するまで行わない（各エージェントも同様で、変更は作業ツリーに残して報告するだけにする）
- ユーザーの指示は、その作業1回分の許可であり、以降の常時の許可ではない
- ユーザーが「PR をマージし、GitHub 上の開発ブランチを削除した」と連絡したら、次の手順でローカルを後片付けして、次の依頼に備える
  1. `main` に切り替えて `origin/main` の最新を取り込む（`git fetch --prune` で削除済みブランチの追跡情報も整理する）
  2. `git diff main <開発ブランチ名>` を実行する
  3. 差分が空なら、内容はすべて `main` に入っているため、`git branch -D` で削除する。スカッシュマージでは履歴が一致せず `git branch -d` が拒否されるため `-D` を使い、報告に「スカッシュマージのため `-D` を使った」旨を添える
  4. 差分が残る場合は `-D` を使わず、差分の概要を報告して指示を待つ（この場合の `-D` はユーザーが指示した場合のみ使う）

## ディレクトリ構成

```text
.claude/
    agents/
        test-agent.md
        implement-agent.md
        review-agent.md
    skills/
        tdd/
            SKILL.md
        tdd-component/
            SKILL.md
    settings.json
.devcontainer/
    devcontainer.json
    Dockerfile
.github/
    workflows/
        ci.yml
.gitignore
CLAUDE.md
README.md
pyproject.toml
uv.lock
config/
    users.example.toml
app/
    __init__.py
    main.py
    params.py
    auth.py
    rate_limit.py
    router/
        __init__.py
        add.py
        subtract.py
        multiply.py
        divide.py
tests/
    unit/
        test_add.py
        test_subtract.py
        test_multiply.py
        test_divide.py
        test_auth.py
        test_rate_counter.py
        test_rate_limit.py
```

`config/`、`app/auth.py`、`app/rate_limit.py`、`tests/unit/test_auth.py`、`tests/unit/test_rate_counter.py`、`tests/unit/test_rate_limit.py` は、認証とレート制限の実装で作る（`/tdd-component` で進める）。

## 使用ツール

- 使用言語: Python 3.12
- パッケージ管理: uv
- 開発環境: Dev Container（Docker Desktop）
- 使用フレームワーク: FastAPI
- リント: Ruff（`S` ルールでセキュリティも検査する）
- 依存パッケージの脆弱性監査: pip-audit（`uvx` で実行し、依存には追加しない）
- 静的チェック: MyPy
- テスト: Pytest

## コーディング規約

- 命名は PEP 8 に従う（変数・関数・メソッドは `snake_case`、定数は `UPPER_SNAKE_CASE`、クラスは `CapWords`）
- PEP 8 の準拠は Ruff の `N` ルールで検証する（設定は `pyproject.toml`）
- 引数名は仕様どおり `a`, `b` に統一する
- 関数名はエンドポイント名と一致させる（例: `divide`）
- テスト関数名は `test_` で始め、観点が分かる名前にする（例: `test_divide_by_zero_returns_422`）
- 全ての関数に型ヒントを付ける（MyPy の strict で検証する）
- `app/` と `tests/` 配下のモジュール・関数・fixture に docstring を付ける（NumPy スタイル、日本語）。テストの docstring は1行で、検証する観点を書く
- docstring には実装の言い換えではなく、仕様上の意味を書く（例: divide は丸め方と、割り切れる場合の型）
- docstring の有無は Ruff の `D` ルールで検証する（設定は `pyproject.toml`）

## 使用コマンド

```bash
uv sync                                            # 依存関係のインストール
uv run uvicorn app.main:app --reload               # 開発サーバー起動
uv run pytest tests/unit/ -v                       # ユニットテスト実行
uv run pytest tests/unit/test_xxx.py::test_name -v # 単一テスト実行
uv run ruff check .                                # lint実行
uv run ruff format --check .                       # フォーマット差分チェック(適用しない)
uv run mypy app/                                   # 型チェック(appディレクトリのみ対象)
uvx pip-audit --disable-pip --no-deps -r <(uv export --locked --no-hashes --no-emit-project -q)  # 依存パッケージの脆弱性監査(bash 用)
```

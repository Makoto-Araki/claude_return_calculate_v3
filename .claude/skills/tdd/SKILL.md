---
name: tdd
description: 指定したエンドポイント（add / subtract / multiply / divide）を、test-agent → implement-agent → review-agent の順に TDD で実装する。レビューは最大3周。
argument-hint: <add|subtract|multiply|divide>
disable-model-invocation: true
---

エンドポイント `$ARGUMENTS` を TDD で実装する。仕様と規約は CLAUDE.md に従う。

## 前提の確認

- `$ARGUMENTS` が `add`、`subtract`、`multiply`、`divide` のいずれかであること。そうでなければ、作業を始めず、ユーザーに確認する。
- 対象のテスト `tests/unit/test_$ARGUMENTS.py` や実装 `app/router/$ARGUMENTS.py` がすでにある場合は、上書きしてよいかをユーザーに確認する。
- エージェントは別のエージェントを呼べないため、この手順はメインのセッションが順番に呼び出して進める。
- コミット、プッシュ、PR 作成は行わない（CLAUDE.md の Git 運用）。変更は作業ツリーに残す。

## 手順

1. **Red**: `test-agent` を呼び、`tests/unit/test_$ARGUMENTS.py` に失敗するテストを書かせる。
   - 渡す内容: 対象のエンドポイント、`tests/` 以外は編集しないこと、既存のテストの構成に合わせること。
   - 報告から確認する: 追加したテスト一覧、失敗の理由が実装がないこと（404、import エラー）であること、仕様解釈で迷った点。
   - テストの件数が報告と食い違う場合は、`uv run pytest tests/unit/test_$ARGUMENTS.py --collect-only -q` で数え直す。
2. **Green**: `implement-agent` を呼び、テストを通す実装を `app/` に書かせる。
   - 渡す内容: 対象のエンドポイント、`tests/` は編集しないこと、既存の `app/router/` の書き方に合わせること、`app/main.py` にルーターを登録すること。
   - 報告から確認する: 作成・変更したファイル、`pytest`（tests/unit/ 全体）、`ruff check`、`ruff format --check`、`mypy` がすべて通過していること。
3. **レビュー**: `review-agent` を呼び、テストと実装をレビューさせる。
   - 渡す内容: 対象のテストと実装のパス、CLAUDE.md の仕様とコーディング規約（docstring を含む）に照らすこと、ファイルを編集しないこと。
4. **判定**:
   - 承認なら、完了の報告に進む。
   - 「要修正」なら、指摘ごとの差し戻し先（test-agent または implement-agent）に、指摘の内容を渡して修正させ、手順3に戻る。
   - 任意の軽微な指摘は、修正するかをユーザーに確認する。

## 中止の条件

次のいずれかなら、作業を止めて報告する。

- レビューを3周しても承認されない。
- 同じ指摘が2周続いた。
- テストが誤っている、または仕様と食い違っていると implement-agent が報告した。
- 仕様が曖昧で、test-agent が質問を返した。

中止の報告には、エンドポイント名、各周の指摘の要約、未解決の指摘、考えられる原因を含める。

## 完了の報告

- エンドポイント名と、レビューを何周で承認されたか。
- Red、Green、レビューの各フェーズの結果（テスト件数、検証コマンドの結果）。
- 未対応の任意の指摘。
- 次の作業の案（ブランチを切ってコミット・プッシュ・PR 作成。ユーザーの指示があるまで行わない）。

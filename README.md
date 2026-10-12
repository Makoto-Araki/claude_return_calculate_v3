# claude_return_calculate_v3 計算APIサーバー

## 目的

2つの正の整数を受け取り、四則演算（加算・減算・乗算・除算）を行う計算APIサーバー。
APIキーによる認証と、ユーザーごとのレート制限（1分あたり60回まで。超えたら 429）を備える。

次の2点を試すための、実験用のリポジトリでもある。

- API の使用レートをユーザーごとに計測し、高すぎるユーザーに使用制限をかける仕組みが成り立つかの確認
- テスト・実装・レビューをそれぞれ担当するエージェントによる、TDD での開発の進め方の確認

本番での利用は想定していない（TLS を使わず HTTP のままで、APIキーが平文で流れるため）。

## 前提

ローカルPCに次をインストールしておく。

- Git
- Docker Desktop（起動しておく）
- Visual Studio Code
- VS Code の拡張機能「Dev Containers」（`ms-vscode-remote.remote-containers`）

## 起動手順

APIサーバーは Dev Container 内で起動する。

1. Docker Desktop を起動し、起動が完了するまで待つ。

2. GitHub からリポジトリを複製する。

   ```bash
   git clone https://github.com/Makoto-Araki/claude_return_calculate_v3.git
   cd claude_return_calculate_v3
   ```

3. VS Code でリポジトリのフォルダを開く。

   ```bash
   code .
   ```

4. 右下に「Reopen in Container」の通知が出たらそれを押す。出ない場合は、コマンドパレット（`Ctrl+Shift+P`）から「Dev Containers: Reopen in Container」を実行する。

5. コンテナのビルドと初期設定が終わるまで待つ。初回はイメージの取得と依存関係のインストール（`uv sync`）に時間がかかる。

6. VS Code のターミナル（コンテナ内）で、ユーザーとAPIキーの設定ファイルを作る。雛形をコピーして、`api_key` を自分で決めた値に書き換える。

   ```bash
   cp config/users.example.toml config/users.toml
   ```

   - `api_key` は、ASCII の文字列にする（ASCII 以外の文字を含むキーは、HTTP ヘッダーの復号の都合で、設定しても一致しない）。
   - `name` と `api_key` は、空にせず、ユーザー間で重複させない。
   - 実際のキーを書いた `config/users.toml` は Git にコミットしない（`.gitignore` に入っている）。
   - このファイルがない、または形式が不正な場合、サーバーは起動時にエラーで止まる。

7. ターミナルで開発サーバーを起動する。

   ```bash
   uv run uvicorn app.main:app --reload
   ```

8. 別のターミナルから、`http://localhost:8000` にアクセスして動作を確認する。ポート 8000 は VS Code が自動でローカルPCに転送する。

## 認証とレート制限

4つのエンドポイントすべてに、APIキー認証とレート制限がかかる。処理は 認証 → レート制限 → 入力検証 の順に行う。

| 状況 | レスポンス |
| ---- | ---------- |
| `X-API-Key` ヘッダーがない、またはキーが違う | 401 `{"detail":"Invalid API key"}` |
| 同じユーザーが1分間に61回目以降を送った | 429 `{"detail":"Rate limit exceeded"}`。`Retry-After` ヘッダーに、制限が解ける（次の1分間が始まる）までの秒数が入る |
| 入力が正の整数でない | 422（認証とレート制限を通ったあとに判定する） |

- 認証には、リクエストヘッダー `X-API-Key` に、`config/users.toml` に書いたキーを入れる。
- 1分間は、時計の分の区切りで決まる（たとえば 12:00:00 から 12:00:59 まで）。次の1分間が始まると、回数は 0 から数え直す。
- 回数はユーザーごとに独立して数える。認証に失敗したリクエストは数えず、入力が不正で 422 になったリクエストは数える。
- 回数はサーバーのメモリで数えるため、サーバーを再起動すると 0 に戻る。
- `/docs` などの自動生成のドキュメントは、API の構成が認証なしで見えないよう、無効にしている。

## 動作確認

`config/users.toml` に書いたキーを、環境変数に入れておく（以降の例の `<キー>` の部分）。

```bash
export API_KEY="<キー>"
```

```bash
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/add?a=1&b=2"        # {"result":3}
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/subtract?a=1&b=3"   # {"result":-2}
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/multiply?a=2&b=3"   # {"result":6}
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/divide?a=6&b=3"     # {"result":2}
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/divide?a=1&b=4"     # {"result":0.3}
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/divide?a=1&b=0"     # 422（b=0 は正の整数でないため）
```

認証とレート制限の確認:

```bash
# キーを付けない: 401
curl -i "http://localhost:8000/add?a=1&b=2"

# 70回続けて送る: その1分間の合計が60回に達するまでは 200、それ以降は 429。
# 直前までに送った分も数えるため、200 の件数は「60 − その1分間にすでに送った回数」になる。
# 分の区切りをまたぐと、数え直されて件数が変わる。
for i in $(seq 1 70); do
  curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $API_KEY" "http://localhost:8000/add?a=1&b=2"
done | sort | uniq -c

# 429 のレスポンスを見る: Retry-After ヘッダーが付いている
curl -i -H "X-API-Key: $API_KEY" "http://localhost:8000/add?a=1&b=2"
```

## 停止方法

- 開発サーバーの停止: ターミナルで `Ctrl+C` を押す。
- Dev Container の終了: VS Code の左下の緑色の表示を押し、「Close Remote Connection」を選ぶ。

## テストと静的チェック

Dev Container 内のターミナルで実行する。

```bash
uv run pytest tests/unit/ -v    # ユニットテスト
uv run ruff check .             # lint
uv run ruff format --check .    # フォーマット差分チェック
uv run mypy app/                # 型チェック
uvx pip-audit --disable-pip --no-deps -r <(uv export --locked --no-hashes --no-emit-project -q)  # 依存パッケージの脆弱性監査
```

テストは実際の `config/users.toml` を読まない。ダミーのキーと、差し替えた時計を使うため、`config/users.toml` がなくても、また実時間を待たずに実行できる。

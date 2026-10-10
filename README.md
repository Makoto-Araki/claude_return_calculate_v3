# claude_return_calculate_v3 計算APIサーバー

## 目的

2つの正の整数を受け取り、四則演算を行うシンプルな計算APIサーバー

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

6. VS Code のターミナル（コンテナ内）で開発サーバーを起動する。

   ```bash
   uv run uvicorn app.main:app --reload
   ```

7. ブラウザまたはターミナルから、ローカルPCの `http://localhost:8000` にアクセスして動作を確認する。ポート 8000 は VS Code が自動でローカルPCに転送する。

## 動作確認

```bash
curl "http://localhost:8000/add?a=1&b=2"        # {"result":3}
curl "http://localhost:8000/subtract?a=1&b=3"   # {"result":-2}
curl "http://localhost:8000/multiply?a=2&b=3"   # {"result":6}
curl "http://localhost:8000/divide?a=6&b=3"     # {"result":2}
curl "http://localhost:8000/divide?a=1&b=4"     # {"result":0.3}
curl "http://localhost:8000/divide?a=1&b=0"     # 422（b=0 は正の整数でないため）
```

ブラウザで `http://localhost:8000/docs` を開くと、API の仕様を確認できる。

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
```

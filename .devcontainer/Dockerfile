FROM mcr.microsoft.com/devcontainers/python:3.12

# uv をコピーして導入する（依存関係の管理とコマンド実行に使う）
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /usr/local/bin/

# 仮想環境をプロジェクト直下の .venv に作る（既定）
ENV UV_LINK_MODE=copy

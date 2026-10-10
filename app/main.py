"""計算 API サーバーのエントリポイント。各演算のルーターを登録する。"""

from fastapi import FastAPI

from app.router import add

app = FastAPI()

app.include_router(add.router)

"""計算 API サーバーのエントリポイント。各演算のルーターを登録する。"""

from fastapi import FastAPI

from app.router import add, divide, multiply, subtract

app = FastAPI()

app.include_router(add.router)
app.include_router(subtract.router)
app.include_router(multiply.router)
app.include_router(divide.router)

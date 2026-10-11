"""計算 API サーバーのエントリポイント。各演算のルーターを登録する。

全エンドポイントに APIキー認証をかける。ユーザー設定は起動時に読み込み、
異常があれば起動を止める。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.auth import authenticate, get_users_path, load_users
from app.router import add, divide, multiply, subtract


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """起動時にユーザー設定を読み込み、異常があれば起動を止める。

    Parameters
    ----------
    application : FastAPI
        起動するアプリケーション。
    """
    application.state.users = load_users(get_users_path())
    try:
        yield
    finally:
        del application.state.users


app = FastAPI(
    lifespan=lifespan,
    dependencies=[Depends(authenticate)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(add.router)
app.include_router(subtract.router)
app.include_router(multiply.router)
app.include_router(divide.router)

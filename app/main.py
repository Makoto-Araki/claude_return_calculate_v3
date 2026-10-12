"""計算 API サーバーのエントリポイント。各演算のルーターを登録する。

全エンドポイントに APIキー認証とユーザーごとのレート制限をかける。
処理順序は 認証 → レート制限 → 入力検証。ユーザー設定は起動時に読み込み、
異常があれば起動を止める。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.auth import authenticate, get_users_path, load_users
from app.rate_counter import RateCounter
from app.rate_limit import rate_limit
from app.router import add, divide, multiply, subtract


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """起動時にユーザー設定を読み込み、異常があれば起動を止める。

    設定の読み込みに成功したあとで、レート制限のカウンターを 1 つ作る。

    Parameters
    ----------
    application : FastAPI
        起動するアプリケーション。
    """
    application.state.users = load_users(get_users_path())
    try:
        application.state.counter = RateCounter()
        try:
            yield
        finally:
            del application.state.counter
    finally:
        del application.state.users


app = FastAPI(
    lifespan=lifespan,
    dependencies=[Depends(authenticate), Depends(rate_limit)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(add.router)
app.include_router(subtract.router)
app.include_router(multiply.router)
app.include_router(divide.router)

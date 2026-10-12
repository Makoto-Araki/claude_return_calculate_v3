"""認証済みユーザーごとのレート制限を、FastAPI の依存関係として提供する。

認証に成功したリクエストだけを 1 回として数え、上限を超えたら 429 を返す。
認証に失敗したリクエストは数えない。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.auth import authenticate
from app.rate_counter import RateCounter


def get_counter(request: Request) -> RateCounter:
    """アプリ全体で共有するレート制限カウンターを返す。

    起動時に作ったカウンターを返す。テストでは依存関係の上書きで差し替える。

    Parameters
    ----------
    request : Request
        現在のリクエスト。

    Returns
    -------
    RateCounter
        アプリ全体で 1 つのカウンター。
    """
    counter: RateCounter = request.app.state.counter
    return counter


def rate_limit(
    user: Annotated[str, Depends(authenticate)],
    counter: Annotated[RateCounter, Depends(get_counter)],
) -> None:
    """認証済みユーザーのリクエストを 1 回と数え、上限を超えたら拒否する。

    どのエンドポイントも 1 回として数え、重みは付けない。入力検証より先に
    評価されるため、後で 422 になるリクエストも数える。

    Parameters
    ----------
    user : str
        認証されたユーザー名。認証に失敗した場合、この関数は呼ばれない。
    counter : RateCounter
        ユーザーごとのリクエスト回数を数えるカウンター。

    Raises
    ------
    HTTPException
        1 ウィンドウ内の上限を超えた場合（429、本文は ``Rate limit exceeded``）。
        ``Retry-After`` ヘッダーに、ウィンドウが終わるまでの残り秒数を付ける。
    """
    decision = counter.hit(user)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after)},
        )

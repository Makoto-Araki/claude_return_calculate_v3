"""multiply エンドポイント（正の整数2つの乗算）を提供するモジュール。"""

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError

from app.params import PositiveInt

router = APIRouter()

_MAX_RESULT = 10**4300
"""返せる積の上限（4300 桁）を超える最小の値。この値以上の積は 422 にする。"""


@router.get("/multiply")
def multiply(
    a: PositiveInt,
    b: PositiveInt,
) -> dict[str, int]:
    """2つの正の整数を乗算して返す。積が 4300 桁を超える場合は 422 になる。

    Parameters
    ----------
    a : int
        被乗数となる正の整数。0 以下、小数、非数値は 422 になる。
    b : int
        乗数となる正の整数。0 以下、小数、非数値は 422 になる。

    Returns
    -------
    dict[str, int]
        乗算結果（a * b）を ``result`` キーに入れた辞書。結果は int で返る。
        積がちょうど 4300 桁なら 200 で返る。

    Raises
    ------
    RequestValidationError
        個々の入力が有効でも、積が 4300 桁を超える場合。
        FastAPI 標準の検証エラー形式（``detail`` 配列）の 422 になる。
    """
    product = a * b
    if product >= _MAX_RESULT:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query",),
                    "msg": "積が 4300 桁を超えるため計算できません",
                }
            ]
        )
    return {"result": product}

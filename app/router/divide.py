"""divide エンドポイント（正の整数2つの除算）を提供するモジュール。"""

import math

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError

from app.params import PositiveInt

router = APIRouter()

_FLOAT_DIGITS_LIMIT = 10**310
"""丸めた商（10 倍した整数）がこの値以上なら float にできないと確定させる閾値。

float の最大値は約 1.8×10^308 であり、これを超える値は文字列化せずに弾く。
"""


def _out_of_float_range() -> RequestValidationError:
    """商が float の範囲を超える場合の、標準形式の検証エラーを作る。

    Returns
    -------
    RequestValidationError
        FastAPI 標準の検証エラー形式（``detail`` 配列）の 422 になる例外。
    """
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("query",),
                "msg": "商が float の範囲を超えるため計算できません",
            }
        ]
    )


@router.get("/divide")
def divide(
    a: PositiveInt,
    b: PositiveInt,
) -> dict[str, int | float]:
    """2つの正の整数を除算して返す。

    割り切れる場合は int、割り切れない場合は小数点第2位を ROUND_HALF_UP
    （四捨五入）で丸めた小数点以下1桁の float を返す。

    Parameters
    ----------
    a : int
        被除数となる正の整数。0 以下、小数、非数値は 422 になる。
    b : int
        除数となる正の整数。0 は正の整数でないため 422 になる。

    Returns
    -------
    dict[str, int | float]
        除算結果を ``result`` キーに入れた辞書。
        割り切れる場合は int（float の範囲を超えても int のまま）。
        割り切れない場合は小数第1位までの float で、丸めた結果が整数値
        （例: 199÷100 は 2.0）でも float のまま返る。
        商が極端に小さく丸めると 0 になる場合は 0.0 を返す。

    Raises
    ------
    RequestValidationError
        割り切れない商を丸めた値が float の範囲を超える場合。
        FastAPI 標準の検証エラー形式（``detail`` 配列）の 422 になる。
    """
    if a % b == 0:
        return {"result": a // b}

    # a / b を 10 倍して四捨五入した整数（商の小数第1位までを表す）。
    # 正の数なので floor(a*10/b + 1/2) が ROUND_HALF_UP と一致する。
    tenths = (a * 20 + b) // (2 * b)
    if tenths >= _FLOAT_DIGITS_LIMIT:
        raise _out_of_float_range()
    whole, fraction = divmod(tenths, 10)
    value = float(f"{whole}.{fraction}")
    if math.isinf(value):
        raise _out_of_float_range()
    return {"result": value}

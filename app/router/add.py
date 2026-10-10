"""add エンドポイント（正の整数2つの加算）を提供するモジュール。"""

from fastapi import APIRouter

from app.params import PositiveInt

router = APIRouter()


@router.get("/add")
def add(
    a: PositiveInt,
    b: PositiveInt,
) -> dict[str, int]:
    """2つの正の整数を加算して返す。

    Parameters
    ----------
    a : int
        1つ目の正の整数。0 以下、小数、非数値は 422 になる。
    b : int
        2つ目の正の整数。0 以下、小数、非数値は 422 になる。

    Returns
    -------
    dict[str, int]
        加算結果を ``result`` キーに入れた辞書。結果は int で返る。
    """
    return {"result": a + b}

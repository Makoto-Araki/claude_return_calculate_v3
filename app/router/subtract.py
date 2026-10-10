"""subtract エンドポイント（正の整数2つの減算）を提供するモジュール。"""

from fastapi import APIRouter

from app.params import PositiveInt

router = APIRouter()


@router.get("/subtract")
def subtract(
    a: PositiveInt,
    b: PositiveInt,
) -> dict[str, int]:
    """2つの正の整数を減算して返す。結果が負数や 0 でも正常として扱う。

    Parameters
    ----------
    a : int
        被減数となる正の整数。0 以下、小数、非数値は 422 になる。
    b : int
        減数となる正の整数。0 以下、小数、非数値は 422 になる。

    Returns
    -------
    dict[str, int]
        減算結果（a - b）を ``result`` キーに入れた辞書。結果は int で返り、
        負数や 0 の場合もエラーにならず 200 で返る。
    """
    return {"result": a - b}

"""全エンドポイントで共通の引数型を定義するモジュール。"""

import re
from typing import Annotated, Any

from fastapi import Query
from pydantic import BeforeValidator

_DIGITS = re.compile(r"[0-9]+")


def _require_integer_notation(value: Any) -> Any:
    """整数表記（数字のみ）の文字列だけを通す。

    Parameters
    ----------
    value : Any
        クエリ文字列から渡された値。

    Returns
    -------
    Any
        整数表記ならそのままの値。

    Raises
    ------
    ValueError
        "1.0" のように値が整数でも小数表記の場合や、数字以外を含む場合。
    """
    if isinstance(value, str) and not _DIGITS.fullmatch(value):
        # 負数は gt=0 でも弾けるが、"-1" のような表記もここで一括して拒否する
        raise ValueError("正の整数の表記ではありません")
    return value


PositiveInt = Annotated[
    int,
    BeforeValidator(_require_integer_notation),
    Query(gt=0),
]
"""正の整数（1 以上）のクエリ引数型。0 以下、小数表記、非数値は 422 になる。"""

"""divide エンドポイント（割り切れれば int、他は小数第1位の float）の仕様を検証する。"""

import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """テスト用の HTTP クライアントを返す。"""
    return TestClient(app)


def test_divide_exact_returns_int_with_200(client: TestClient) -> None:
    """割り切れる除算が 200 と整数の result で返ること。"""
    response = client.get("/divide", params={"a": 10, "b": 5})
    assert response.status_code == 200
    assert response.json() == {"result": 2}


def test_divide_exact_result_is_int(client: TestClient) -> None:
    """割り切れる場合の result が int 型（bool や float でない）で返ること。"""
    result = client.get("/divide", params={"a": 10, "b": 5}).json()["result"]
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_divide_same_numbers_returns_int_one(client: TestClient) -> None:
    """同じ数どうしの除算が整数 1 で返ること。"""
    result = client.get("/divide", params={"a": 7, "b": 7}).json()["result"]
    assert result == 1
    assert isinstance(result, int)


def test_divide_response_has_only_result_key(client: TestClient) -> None:
    """正常時のレスポンスが result キーのみであること。"""
    response = client.get("/divide", params={"a": 6, "b": 3})
    assert list(response.json().keys()) == ["result"]


def test_divide_inexact_result_is_float(client: TestClient) -> None:
    """割り切れない場合の result が float 型で返ること。"""
    result = client.get("/divide", params={"a": 1, "b": 3}).json()["result"]
    assert isinstance(result, float)


def test_divide_smaller_dividend_returns_fraction(client: TestClient) -> None:
    """被除数が除数より小さい場合（1÷2）に 0.5 の float が返ること。"""
    response = client.get("/divide", params={"a": 1, "b": 2})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 0.5
    assert isinstance(result, float)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (1, 3, 0.3),
        (2, 3, 0.7),
        (1, 4, 0.3),
        (1, 20, 0.1),
        (7, 20, 0.4),
        (1, 8, 0.1),
        (3, 8, 0.4),
    ],
    ids=[
        "one_third_down",
        "two_thirds_up",
        "quarter_half_up_not_bankers",
        "one_twentieth_half_up",
        "seven_twentieths_half_up",
        "one_eighth_second_digit_2_down",
        "three_eighths_up",
    ],
)
def test_divide_rounds_half_up_to_one_decimal(
    client: TestClient, a: int, b: int, expected: float
) -> None:
    """割り切れない商が ROUND_HALF_UP で小数第1位に丸められた float で返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == expected
    assert isinstance(result, float)


def test_divide_inexact_rounding_to_integer_value_stays_float(
    client: TestClient,
) -> None:
    """割り切れないが丸めた値が整数値（199÷100 → 2.0）の場合は float のまま返ること。"""
    response = client.get("/divide", params={"a": 199, "b": 100})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 2.0
    assert isinstance(result, float)


@pytest.mark.parametrize(
    ("a", "b"),
    [("1", "30"), ("1", "1" + "0" * 4299)],
    ids=["one_thirtieth", "b_4300_digits"],
)
def test_divide_tiny_quotient_rounds_to_zero_float(
    client: TestClient, a: str, b: str
) -> None:
    """極端に小さい商は丸めて 0.0 となり、int と区別して float で返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 0.0
    assert isinstance(result, float)


def test_divide_large_integer_part_keeps_precision(client: TestClient) -> None:
    """商の整数部が 28 桁を超えても 500 にならず ROUND_HALF_UP の結果が返ること。"""
    response = client.get("/divide", params={"a": 10**30 + 1, "b": 3})
    assert response.status_code == 200
    assert response.json()["result"] == float("333333333333333333333333333333.7")


def test_divide_inexact_quotient_within_float_range_returns_200(
    client: TestClient,
) -> None:
    """割り切れない商が float の範囲内（約 3.3×10^307）なら 200 と float が返ること。"""
    response = client.get("/divide", params={"a": 10**308, "b": 3})
    assert response.status_code == 200
    result = response.json()["result"]
    assert isinstance(result, float)
    assert result > 3.3e307


@pytest.mark.parametrize(
    ("a", "b"),
    [(10**309, 3), (10**400, 3)],
    ids=["quotient_3e308", "quotient_3e399"],
)
def test_divide_inexact_quotient_exceeding_float_range_returns_422(
    client: TestClient, a: int, b: int
) -> None:
    """割り切れない商が float の範囲外なら 500 ではなく 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": str(a), "b": str(b)})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_divide_exact_quotient_exceeding_float_range_returns_int(
    client: TestClient,
) -> None:
    """割り切れる場合は float の範囲を超えても 200 と int の result が返ること。"""
    a = "1" + "0" * 400
    b = "1" + "0" * 100
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 10**300
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_divide_exact_quotient_of_4300_digits_returns_200(client: TestClient) -> None:
    """割り切れる商がちょうど 4300 桁の場合は 200 と int の result が返ること。"""
    a = "1" + "0" * 4299
    response = client.get("/divide", params={"a": a, "b": "1"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 10**4299
    assert isinstance(result, int)


def test_divide_input_a_of_4301_digits_returns_422(client: TestClient) -> None:
    """入力 a が 4301 桁の場合は 422 と detail が返ること。"""
    a = "1" + "0" * 4300
    response = client.get("/divide", params={"a": a, "b": "1"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_divide_input_b_of_4300_digits_returns_200(client: TestClient) -> None:
    """入力 b がちょうど 4300 桁の場合は入力として受理され 200 になること。"""
    b = "1" + "0" * 4299
    response = client.get("/divide", params={"a": b, "b": b})
    assert response.status_code == 200
    assert response.json() == {"result": 1}


def test_divide_input_b_of_4301_digits_returns_422(client: TestClient) -> None:
    """入力 b が 4301 桁の場合は 422 と detail が返ること。"""
    b = "1" + "0" * 4300
    response = client.get("/divide", params={"a": "1", "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_divide_input_a_of_4300_digits_returns_200(client: TestClient) -> None:
    """入力 a がちょうど 4300 桁の場合は 200 と a と等しい result が返ること。"""
    a = "9" * 4300
    response = client.get("/divide", params={"a": a, "b": "1"})
    assert response.status_code == 200
    assert response.json()["result"] == int(a)


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (0, 0)],
    ids=["a_zero", "b_zero", "both_zero"],
)
def test_divide_zero_returns_422(client: TestClient, a: int, b: int) -> None:
    """0（b=0 を含む）は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [(-1, 2), (1, -2), (-1, -2)],
    ids=["a_negative", "b_negative", "both_negative"],
)
def test_divide_negative_input_returns_422(client: TestClient, a: int, b: int) -> None:
    """負数の入力は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("1.5", "2"), ("1", "2.5"), ("1.0", "2"), ("2", "1.0")],
    ids=[
        "a_decimal",
        "b_decimal",
        "a_decimal_integral_value",
        "b_decimal_integral_value",
    ],
)
def test_divide_decimal_returns_422(client: TestClient, a: str, b: str) -> None:
    """小数は整数でないため 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("abc", "2"), ("1", "abc")],
    ids=["a_string", "b_string"],
)
def test_divide_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """文字列は整数でないため 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("", "2"), ("1", "")],
    ids=["a_empty", "b_empty"],
)
def test_divide_empty_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """空文字は整数でないため 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_divide_missing_b_returns_422(client: TestClient) -> None:
    """引数 b が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": 1})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_divide_missing_a_returns_422(client: TestClient) -> None:
    """引数 a が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/divide", params={"b": 2})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_divide_missing_both_returns_422(client: TestClient) -> None:
    """引数 a も b も欠落している場合に 422 と detail が返ること。"""
    response = client.get("/divide")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("9" * 5000, "1"), ("1", "9" * 5000)],
    ids=["a_huge", "b_huge"],
)
def test_divide_huge_digit_string_returns_422(
    client: TestClient, a: str, b: str
) -> None:
    """桁数が極端に大きい数字文字列は 500 ではなく 422 と detail が返ること。"""
    response = client.get("/divide", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(249, 1000, 0.2), (95, 100, 1.0), (995, 100, 10.0)],
    ids=["below_half_rounds_down", "carry_to_one", "carry_to_ten"],
)
def test_divide_rounding_boundary_returns_float(
    client: TestClient, a: int, b: int, expected: float
) -> None:
    """丸めの境界（5 未満の切り捨てと繰り上がり）が float で返ること。"""
    result = client.get("/divide", params={"a": a, "b": b}).json()["result"]
    assert result == expected
    assert isinstance(result, float)


def test_divide_float_max_boundary_returns_200(client: TestClient) -> None:
    """丸めた値がちょうど float の最大値になる除算が inf にならず 200 で返ること。"""
    max_int = int(sys.float_info.max)
    response = client.get("/divide", params={"a": max_int * 10 + 1, "b": 10})
    assert response.status_code == 200
    assert response.json()["result"] == sys.float_info.max


def test_divide_just_over_float_max_returns_422(client: TestClient) -> None:
    """浮動小数点の範囲を超える除算結果が 422 と detail 配列で返ること。"""
    max_int = int(sys.float_info.max)
    a = (max_int + 2**970) * 10 + 1
    response = client.get("/divide", params={"a": a, "b": 10})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)

"""multiply エンドポイント（正の整数2つの乗算、積が4300桁超は422）の仕様を検証する。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(api_key: str) -> TestClient:
    """有効な X-API-Key を付けたテスト用の HTTP クライアントを返す。"""
    return TestClient(app, headers={"X-API-Key": api_key})


def test_multiply_returns_product_with_200(client: TestClient) -> None:
    """正の整数2つの乗算結果が 200 と result で返ること。"""
    response = client.get("/multiply", params={"a": 3, "b": 4})
    assert response.status_code == 200
    assert response.json() == {"result": 12}


def test_multiply_result_is_int(client: TestClient) -> None:
    """乗算結果が int 型で返ること。"""
    result = client.get("/multiply", params={"a": 3, "b": 4}).json()["result"]
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_multiply_response_has_only_result_key(client: TestClient) -> None:
    """正常時のレスポンスが result キーのみであること。"""
    response = client.get("/multiply", params={"a": 2, "b": 5})
    assert list(response.json().keys()) == ["result"]


def test_multiply_large_integers(client: TestClient) -> None:
    """桁数の大きい積でも正しく乗算できること。"""
    response = client.get("/multiply", params={"a": 1000000, "b": 2000000})
    assert response.status_code == 200
    assert response.json() == {"result": 2000000000000}


def test_multiply_product_of_4300_digits_returns_200(client: TestClient) -> None:
    """積がちょうど 4300 桁の場合は 200 と 4300 桁の result が返ること。"""
    response = client.get("/multiply", params={"a": str(10**2149), "b": str(10**2150)})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result == 10**4299
    assert len(str(result)) == 4300


def test_multiply_product_of_4301_digits_returns_422(client: TestClient) -> None:
    """積が 4301 桁になる場合は 500 ではなく 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": str(10**2150), "b": str(10**2150)})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_product_exceeding_4300_digits_from_valid_inputs_returns_422(
    client: TestClient,
) -> None:
    """各入力が 4300 桁以内でも積が 4300 桁を超えれば 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": "9" * 4000, "b": "9" * 4000})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_input_of_4300_digits_returns_200(client: TestClient) -> None:
    """入力 a がちょうど 4300 桁の場合は 200 と a と等しい result が返ること。"""
    a = "1" + "0" * 4299
    response = client.get("/multiply", params={"a": a, "b": "1"})
    assert response.status_code == 200
    assert response.json()["result"] == int(a)


def test_multiply_input_of_4301_digits_returns_422(client: TestClient) -> None:
    """入力 a が 4301 桁の場合は 422 と detail が返ること。"""
    a = "1" + "0" * 4300
    response = client.get("/multiply", params={"a": a, "b": "1"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_max_4300_digit_product_returns_200(client: TestClient) -> None:
    """4300 桁の最大値（全桁 9）と 1 の積が 200 と 4300 桁の result で返ること。"""
    response = client.get("/multiply", params={"a": "9" * 4300, "b": "1"})
    assert response.status_code == 200
    assert len(str(response.json()["result"])) == 4300


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (0, 0)],
    ids=["a_zero", "b_zero", "both_zero"],
)
def test_multiply_zero_returns_422(client: TestClient, a: int, b: int) -> None:
    """0 は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [(-1, 2), (1, -2), (-1, -2)],
    ids=["a_negative", "b_negative", "both_negative"],
)
def test_multiply_negative_input_returns_422(
    client: TestClient, a: int, b: int
) -> None:
    """負数の入力は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("1.5", "2"), ("1", "2.5"), ("1.0", "2")],
    ids=["a_decimal", "b_decimal", "a_decimal_integral_value"],
)
def test_multiply_decimal_returns_422(client: TestClient, a: str, b: str) -> None:
    """小数は整数でないため 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("abc", "2"), ("1", "abc")],
    ids=["a_string", "b_string"],
)
def test_multiply_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """文字列は整数でないため 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_missing_b_returns_422(client: TestClient) -> None:
    """引数 b が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": 1})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_missing_a_returns_422(client: TestClient) -> None:
    """引数 a が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/multiply", params={"b": 2})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_multiply_missing_both_returns_422(client: TestClient) -> None:
    """引数 a も b も欠落している場合に 422 と detail が返ること。"""
    response = client.get("/multiply")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("9" * 5000, "1"), ("1", "9" * 5000)],
    ids=["a_huge", "b_huge"],
)
def test_multiply_huge_digit_string_returns_422(
    client: TestClient, a: str, b: str
) -> None:
    """桁数が極端に大きい数字文字列は 500 ではなく 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("", "2"), ("1", "")],
    ids=["a_empty", "b_empty"],
)
def test_multiply_empty_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """空文字は整数でないため 422 と detail が返ること。"""
    response = client.get("/multiply", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()

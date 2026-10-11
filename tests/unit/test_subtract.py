"""subtract エンドポイント（正の整数2つの減算、負数の結果は許容）の仕様を検証する。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(api_key: str) -> TestClient:
    """有効な X-API-Key を付けたテスト用の HTTP クライアントを返す。"""
    return TestClient(app, headers={"X-API-Key": api_key})


def test_subtract_returns_difference_with_200(client: TestClient) -> None:
    """正の整数2つの減算結果が 200 と result で返ること。"""
    response = client.get("/subtract", params={"a": 5, "b": 3})
    assert response.status_code == 200
    assert response.json() == {"result": 2}


def test_subtract_result_is_int(client: TestClient) -> None:
    """減算結果が int 型で返ること。"""
    result = client.get("/subtract", params={"a": 5, "b": 3}).json()["result"]
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_subtract_response_has_only_result_key(client: TestClient) -> None:
    """正常時のレスポンスが result キーのみであること。"""
    response = client.get("/subtract", params={"a": 20, "b": 10})
    assert list(response.json().keys()) == ["result"]


def test_subtract_large_integers(client: TestClient) -> None:
    """大きな正の整数でも正しく減算できること。"""
    response = client.get("/subtract", params={"a": 3000000, "b": 1000000})
    assert response.status_code == 200
    assert response.json() == {"result": 2000000}


def test_subtract_negative_result_returns_200(client: TestClient) -> None:
    """結果が負数になる場合も 200 と負数の result が返ること。"""
    response = client.get("/subtract", params={"a": 1, "b": 2})
    assert response.status_code == 200
    assert response.json() == {"result": -1}


def test_subtract_negative_result_is_int(client: TestClient) -> None:
    """結果が負数でも int 型で返ること。"""
    result = client.get("/subtract", params={"a": 1, "b": 3}).json()["result"]
    assert result == -2
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_subtract_zero_result_returns_200(client: TestClient) -> None:
    """引数が等しく結果が 0 になる場合も 200 と result 0 が返ること。"""
    response = client.get("/subtract", params={"a": 4, "b": 4})
    assert response.status_code == 200
    assert response.json() == {"result": 0}


def test_subtract_zero_result_is_int(client: TestClient) -> None:
    """結果が 0 の場合も int 型で返ること。"""
    result = client.get("/subtract", params={"a": 4, "b": 4}).json()["result"]
    assert isinstance(result, int)
    assert not isinstance(result, bool)


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (0, 0)],
    ids=["a_zero", "b_zero", "both_zero"],
)
def test_subtract_zero_returns_422(client: TestClient, a: int, b: int) -> None:
    """0 は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [(-1, 2), (1, -2), (-1, -2)],
    ids=["a_negative", "b_negative", "both_negative"],
)
def test_subtract_negative_input_returns_422(
    client: TestClient, a: int, b: int
) -> None:
    """負数の入力は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("1.5", "2"), ("1", "2.5"), ("1.0", "2")],
    ids=["a_decimal", "b_decimal", "a_decimal_integral_value"],
)
def test_subtract_decimal_returns_422(client: TestClient, a: str, b: str) -> None:
    """小数は整数でないため 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("abc", "2"), ("1", "abc")],
    ids=["a_string", "b_string"],
)
def test_subtract_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """文字列は整数でないため 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_subtract_missing_b_returns_422(client: TestClient) -> None:
    """引数 b が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": 1})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_subtract_missing_a_returns_422(client: TestClient) -> None:
    """引数 a が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/subtract", params={"b": 2})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_subtract_missing_both_returns_422(client: TestClient) -> None:
    """引数 a も b も欠落している場合に 422 と detail が返ること。"""
    response = client.get("/subtract")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("9" * 5000, "1"), ("1", "9" * 5000)],
    ids=["a_huge", "b_huge"],
)
def test_subtract_huge_digit_string_returns_422(
    client: TestClient, a: str, b: str
) -> None:
    """桁数が極端に大きい数字文字列は 500 ではなく 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("", "2"), ("1", "")],
    ids=["a_empty", "b_empty"],
)
def test_subtract_empty_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """空文字は整数でないため 422 と detail が返ること。"""
    response = client.get("/subtract", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()

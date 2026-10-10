"""add エンドポイント（正の整数2つの加算）の仕様を検証する。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(api_key: str) -> TestClient:
    """有効な X-API-Key を付けたテスト用の HTTP クライアントを返す。"""
    return TestClient(app, headers={"X-API-Key": api_key})


def test_add_returns_sum_with_200(client: TestClient) -> None:
    """正の整数2つの加算結果が 200 と result で返ること。"""
    response = client.get("/add", params={"a": 1, "b": 2})
    assert response.status_code == 200
    assert response.json() == {"result": 3}


def test_add_result_is_int(client: TestClient) -> None:
    """加算結果が int 型で返ること。"""
    result = client.get("/add", params={"a": 1, "b": 2}).json()["result"]
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_add_response_has_only_result_key(client: TestClient) -> None:
    """正常時のレスポンスが result キーのみであること。"""
    response = client.get("/add", params={"a": 10, "b": 20})
    assert list(response.json().keys()) == ["result"]


def test_add_large_integers(client: TestClient) -> None:
    """大きな正の整数でも正しく加算できること。"""
    response = client.get("/add", params={"a": 1000000, "b": 2000000})
    assert response.status_code == 200
    assert response.json() == {"result": 3000000}


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (0, 0)],
    ids=["a_zero", "b_zero", "both_zero"],
)
def test_add_zero_returns_422(client: TestClient, a: int, b: int) -> None:
    """0 は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [(-1, 2), (1, -2), (-1, -2)],
    ids=["a_negative", "b_negative", "both_negative"],
)
def test_add_negative_returns_422(client: TestClient, a: int, b: int) -> None:
    """負数は正の整数でないため 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("1.5", "2"), ("1", "2.5"), ("1.0", "2")],
    ids=["a_decimal", "b_decimal", "a_decimal_integral_value"],
)
def test_add_decimal_returns_422(client: TestClient, a: str, b: str) -> None:
    """小数は整数でないため 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("abc", "2"), ("1", "abc")],
    ids=["a_string", "b_string"],
)
def test_add_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """文字列は整数でないため 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_add_missing_b_returns_422(client: TestClient) -> None:
    """引数 b が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/add", params={"a": 1})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_add_missing_a_returns_422(client: TestClient) -> None:
    """引数 a が欠落している場合に 422 と detail が返ること。"""
    response = client.get("/add", params={"b": 2})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_add_missing_both_returns_422(client: TestClient) -> None:
    """引数 a も b も欠落している場合に 422 と detail が返ること。"""
    response = client.get("/add")
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("9" * 5000, "1"), ("1", "9" * 5000)],
    ids=["a_huge", "b_huge"],
)
def test_add_huge_digit_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """桁数が極端に大きい数字文字列は 500 ではなく 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("a", "b"),
    [("", "2"), ("1", "")],
    ids=["a_empty", "b_empty"],
)
def test_add_empty_string_returns_422(client: TestClient, a: str, b: str) -> None:
    """空文字は整数でないため 422 と detail が返ること。"""
    response = client.get("/add", params={"a": a, "b": b})
    assert response.status_code == 422
    assert "detail" in response.json()

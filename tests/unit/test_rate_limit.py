"""rate-limit（ユーザーごとの 429、Retry-After、処理順序）の仕様を検証する。"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import get_users
from app.main import app
from app.rate_counter import RATE_LIMIT, RateCounter
from app.rate_limit import get_counter
from tests.fake_clock import FakeClock

ALICE_KEY = "dummy-key-for-alice"
BOB_KEY = "dummy-key-for-bob"
TOO_MANY_BODY = {"detail": "Rate limit exceeded"}
VALID_TOML = f"""
[[users]]
name = "alice"
api_key = "{ALICE_KEY}"

[[users]]
name = "bob"
api_key = "{BOB_KEY}"
"""
ENDPOINTS = ["/add", "/subtract", "/multiply", "/divide"]
OK_PARAMS = {"a": 6, "b": 3}
BAD_PARAMS = {"a": 0, "b": 3}


@pytest.fixture
def alice() -> TestClient:
    """ユーザー alice のキーを付けたテスト用の HTTP クライアントを返す。"""
    return TestClient(app, headers={"X-API-Key": ALICE_KEY})


@pytest.fixture
def bob() -> TestClient:
    """ユーザー bob のキーを付けたテスト用の HTTP クライアントを返す。"""
    return TestClient(app, headers={"X-API-Key": BOB_KEY})


@pytest.fixture
def anon() -> TestClient:
    """キーを付けないテスト用の HTTP クライアントを返す。"""
    return TestClient(app)


def use_up(client: TestClient, path: str = "/add", times: int = RATE_LIMIT) -> None:
    """指定回数だけリクエストを送り、枠を使い切る。"""
    for _ in range(times):
        client.get(path, params=OK_PARAMS)


# --- 上限 ---


def test_first_to_60th_requests_return_200(alice: TestClient) -> None:
    """同一ウィンドウの 1 回目から 60 回目までが 200 になること。"""
    for _ in range(60):
        assert alice.get("/add", params=OK_PARAMS).status_code == 200


def test_60th_request_is_still_200(alice: TestClient) -> None:
    """60 回目ちょうどのリクエストが 200 であること。"""
    use_up(alice, times=59)
    assert alice.get("/add", params=OK_PARAMS).status_code == 200


def test_61st_request_returns_429_with_body(alice: TestClient) -> None:
    """61 回目が 429 になり、本文が仕様どおりであること。"""
    use_up(alice)
    response = alice.get("/add", params=OK_PARAMS)
    assert response.status_code == 429
    assert response.json() == TOO_MANY_BODY


def test_requests_after_61st_keep_returning_429(alice: TestClient) -> None:
    """62 回目以降も同じウィンドウ内は 429 のままであること。"""
    use_up(alice)
    for _ in range(5):
        response = alice.get("/add", params=OK_PARAMS)
        assert response.status_code == 429
        assert response.json() == TOO_MANY_BODY


# --- Retry-After ---


@pytest.mark.parametrize(
    ("now", "expected"),
    [(0.0, "60"), (30.0, "30"), (59.5, "1")],
)
def test_retry_after_is_remaining_seconds(
    alice: TestClient, fake_clock: FakeClock, now: float, expected: str
) -> None:
    """429 の Retry-After がウィンドウ終了までの残り秒数の文字列であること。"""
    fake_clock.now = now
    use_up(alice)
    response = alice.get("/add", params=OK_PARAMS)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == expected


def test_200_response_has_no_retry_after(alice: TestClient) -> None:
    """200 のレスポンスに Retry-After が付かないこと。"""
    response = alice.get("/add", params=OK_PARAMS)
    assert response.status_code == 200
    assert "retry-after" not in response.headers


# --- ウィンドウの切り替え ---


def test_next_window_allows_requests_again(
    alice: TestClient, fake_clock: FakeClock
) -> None:
    """次のウィンドウに進むと再び 60 回まで 200 になり、61 回目は 429 になること。"""
    use_up(alice)
    assert alice.get("/add", params=OK_PARAMS).status_code == 429
    fake_clock.now = 60.0
    for _ in range(60):
        assert alice.get("/add", params=OK_PARAMS).status_code == 200
    assert alice.get("/add", params=OK_PARAMS).status_code == 429


# --- ユーザーごとに独立 ---


def test_other_user_is_not_limited_by_alice(alice: TestClient, bob: TestClient) -> None:
    """ユーザー alice が上限に達して 429 でも、bob は 200 になること。"""
    use_up(alice)
    assert alice.get("/add", params=OK_PARAMS).status_code == 429
    assert bob.get("/add", params=OK_PARAMS).status_code == 200


def test_other_user_gets_full_60_requests(alice: TestClient, bob: TestClient) -> None:
    """ユーザー alice が上限でも bob は 60 回まで 200 で、61 回目が 429 になること。"""
    use_up(alice)
    for _ in range(60):
        assert bob.get("/add", params=OK_PARAMS).status_code == 200
    assert bob.get("/add", params=OK_PARAMS).status_code == 429


# --- 4 つのエンドポイント ---


def test_endpoints_share_one_count_without_weight(alice: TestClient) -> None:
    """4 つを 15 回ずつ（計 60 回）呼ぶと、次の 1 回が 429 になること。"""
    for path in ENDPOINTS:
        for _ in range(15):
            assert alice.get(path, params=OK_PARAMS).status_code == 200
    assert alice.get("/add", params=OK_PARAMS).status_code == 429


@pytest.mark.parametrize("path", ENDPOINTS)
def test_every_endpoint_returns_429_after_limit(alice: TestClient, path: str) -> None:
    """上限に達した後は、どのエンドポイントも 429 になること。"""
    use_up(alice)
    response = alice.get(path, params=OK_PARAMS)
    assert response.status_code == 429
    assert response.json() == TOO_MANY_BODY


@pytest.mark.parametrize("path", ENDPOINTS)
def test_each_endpoint_counts_as_one_request(alice: TestClient, path: str) -> None:
    """どのエンドポイントも 1 回のリクエストを 1 回として数えること。"""
    use_up(alice, path, times=59)
    assert alice.get(path, params=OK_PARAMS).status_code == 200
    assert alice.get(path, params=OK_PARAMS).status_code == 429


# --- 処理順序 ---


def test_unauthenticated_invalid_input_returns_401(anon: TestClient) -> None:
    """未認証で a=0 を送ると 422 ではなく 401 になること。"""
    assert anon.get("/add", params=BAD_PARAMS).status_code == 401


def test_over_limit_invalid_input_returns_429_not_422(alice: TestClient) -> None:
    """認証済みで枠超過のときに a=0 を送ると 422 ではなく 429 になること。"""
    use_up(alice)
    response = alice.get("/add", params=BAD_PARAMS)
    assert response.status_code == 429
    assert response.json() == TOO_MANY_BODY


def test_within_limit_invalid_input_returns_422(alice: TestClient) -> None:
    """認証済みで枠内のときに a=0 を送ると 422 になること。"""
    response = alice.get("/add", params=BAD_PARAMS)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_unauthenticated_returns_401_even_if_others_are_over_limit(
    alice: TestClient, anon: TestClient
) -> None:
    """他のユーザーが枠超過でも、キーなしのリクエストは 429 ではなく 401 になること。"""
    use_up(alice)
    assert anon.get("/add", params=OK_PARAMS).status_code == 401


def test_wrong_key_returns_401_even_if_others_are_over_limit(
    alice: TestClient,
) -> None:
    """他のユーザーが枠超過でも、間違ったキーは 429 ではなく 401 になること。"""
    use_up(alice)
    response = alice.get("/add", params=OK_PARAMS, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


# --- 422 も数える ---


def test_invalid_input_requests_are_counted(alice: TestClient) -> None:
    """a=0（422）を 60 回送ると、正しい入力の 61 回目が 429 になること。"""
    for _ in range(60):
        assert alice.get("/add", params=BAD_PARAMS).status_code == 422
    assert alice.get("/add", params=OK_PARAMS).status_code == 429


# --- 認証に失敗したリクエストは数えない ---


def test_failed_auth_requests_are_not_counted(
    anon: TestClient, counter: RateCounter
) -> None:
    """キーなし・間違ったキー・空のキーを計 100 回送っても、カウントが増えないこと。"""
    headers_list: list[dict[str, str]] = [
        {},
        {"X-API-Key": "wrong-key"},
        {"X-API-Key": ""},
    ]
    sent = 0
    while sent < 100:
        for headers in headers_list:
            response = anon.get("/add", params=OK_PARAMS, headers=headers)
            assert response.status_code == 401
            sent += 1
    assert counter.size() == 0


def test_failed_auth_requests_do_not_consume_users_quota(
    alice: TestClient, bob: TestClient, anon: TestClient
) -> None:
    """401 を繰り返しても、alice も bob も 60 回まで 200 になること。"""
    for _ in range(100):
        assert anon.get("/add", params=OK_PARAMS).status_code == 401
    for _ in range(60):
        assert alice.get("/add", params=OK_PARAMS).status_code == 200
    for _ in range(60):
        assert bob.get("/add", params=OK_PARAMS).status_code == 200


# --- 429 に内部情報を出さない ---


def test_429_body_and_headers_do_not_contain_key(alice: TestClient) -> None:
    """429 の本文とヘッダーの値に、送信したキーが含まれないこと。"""
    use_up(alice)
    response = alice.get("/add", params=OK_PARAMS)
    assert response.status_code == 429
    assert ALICE_KEY not in response.text
    assert all(ALICE_KEY not in value for value in response.headers.values())


def test_429_headers_have_no_internal_info(alice: TestClient) -> None:
    """429 のヘッダーが content-length・content-type・retry-after だけであること。"""
    use_up(alice)
    response = alice.get("/add", params=OK_PARAMS)
    assert response.status_code == 429
    assert set(response.headers) <= {"content-length", "content-type", "retry-after"}


# --- 起動時のカウンター ---


def test_startup_creates_rate_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """起動すると app.state.counter が RateCounter のインスタンスになること。"""
    path = tmp_path / "users.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    with TestClient(app):
        assert isinstance(app.state.counter, RateCounter)


def test_restart_creates_new_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2 回起動すると別のカウンターになること（再起動でカウントが消える）。"""
    path = tmp_path / "users.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    with TestClient(app):
        first = app.state.counter
    with TestClient(app):
        second = app.state.counter
    assert first is not second


def test_shutdown_removes_counter_from_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """終了後は app.state にカウンターが残らないこと。"""
    path = tmp_path / "users.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    with TestClient(app):
        pass
    assert not hasattr(app.state, "counter")


# --- 起動時に作ったカウンターを使う ---


@pytest.fixture
def started_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """依存関係の差し替えを外し、lifespan で起動した alice 用のクライアントを返す。"""
    path = tmp_path / "users.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    app.dependency_overrides.pop(get_counter, None)
    app.dependency_overrides.pop(get_users, None)
    with TestClient(app, headers={"X-API-Key": ALICE_KEY}) as client:
        yield client


def test_request_is_counted_by_startup_counter(started_client: TestClient) -> None:
    """起動時に作ったカウンターに、リクエストが 1 回として数えられること。"""
    assert started_client.get("/add", params=OK_PARAMS).status_code == 200
    assert app.state.counter.size() == 1


def test_requests_share_one_startup_counter(started_client: TestClient) -> None:
    """同じユーザーの複数のリクエストが、同じカウンターを共有すること。"""
    started_client.get("/add", params=OK_PARAMS)
    started_client.get("/add", params=OK_PARAMS)
    assert app.state.counter.size() == 1


def test_replaced_state_counter_is_used_on_each_request(
    started_client: TestClient, fake_clock: FakeClock
) -> None:
    """app.state.counter を置き換えると、次のリクエストから置換後が使われること。"""
    original = app.state.counter
    replaced = RateCounter(clock=fake_clock)
    app.state.counter = replaced
    for _ in range(RATE_LIMIT):
        assert started_client.get("/add", params=OK_PARAMS).status_code == 200
    assert started_client.get("/add", params=OK_PARAMS).status_code == 429
    assert replaced.size() == 1
    assert original.size() == 0

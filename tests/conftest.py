"""テスト全体で共有する fixture（ダミーのユーザーとキーの注入）を置く。"""

from collections.abc import Iterator

import pytest

from app.auth import get_users
from app.main import app
from app.rate_counter import RateCounter
from app.rate_limit import get_counter
from tests.fake_clock import FakeClock

DUMMY_USERS = {
    "dummy-key-for-alice": "alice",
    "dummy-key-for-bob": "bob",
}


@pytest.fixture
def api_key() -> str:
    """認証に通るダミーの API キー（alice 用）を返す。"""
    return "dummy-key-for-alice"


@pytest.fixture(autouse=True)
def override_users() -> Iterator[None]:
    """実際の設定ファイルを読まず、ダミーのユーザーを注入し、テスト後に元へ戻す。"""
    app.dependency_overrides[get_users] = lambda: dict(DUMMY_USERS)
    yield
    app.dependency_overrides.pop(get_users, None)


@pytest.fixture
def fake_clock() -> FakeClock:
    """時刻 0.0 から始まる差し替え用の時計を返す。"""
    return FakeClock()


@pytest.fixture
def counter(fake_clock: FakeClock) -> RateCounter:
    """差し替え用の時計を使う、テストごとに新しいカウンターを返す。"""
    return RateCounter(clock=fake_clock)


@pytest.fixture(autouse=True)
def override_counter(counter: RateCounter) -> Iterator[None]:
    """テストごとに新しいカウンターを注入し、テスト後に元へ戻す。"""
    app.dependency_overrides[get_counter] = lambda: counter
    yield
    app.dependency_overrides.pop(get_counter, None)

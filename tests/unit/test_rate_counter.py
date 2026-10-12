"""rate-counter（ユーザーごとの固定ウィンドウのカウンター）の仕様を検証する。"""

import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.rate_counter import RATE_LIMIT, WINDOW_SECONDS, RateCounter


class FakeClock:
    """テストから進められる、差し替え用の時計。"""

    def __init__(self, now: float = 0.0) -> None:
        """現在時刻（UNIX 時間の秒）の初期値を設定する。"""
        self.now = now

    def __call__(self) -> float:
        """現在時刻を返す。"""
        return self.now


@pytest.fixture
def fake_clock() -> FakeClock:
    """時刻 0.0 から始まる差し替え用の時計を返す。"""
    return FakeClock()


@pytest.fixture
def counter(fake_clock: FakeClock) -> RateCounter:
    """差し替え用の時計を使う、テストごとに新しいカウンターを返す。"""
    return RateCounter(clock=fake_clock)


def test_rate_limit_constant_is_60() -> None:
    """1 ウィンドウあたりの上限回数が 60 であること。"""
    assert RATE_LIMIT == 60


def test_window_seconds_constant_is_60() -> None:
    """ウィンドウの長さが 60 秒であること。"""
    assert WINDOW_SECONDS == 60


def test_first_to_60th_hits_are_allowed(counter: RateCounter) -> None:
    """同一ウィンドウの 1 回目から 60 回目までが許可されること。"""
    for _ in range(60):
        assert counter.hit("alice").allowed is True


def test_61st_hit_is_denied(counter: RateCounter) -> None:
    """同一ウィンドウの 61 回目が拒否されること。"""
    for _ in range(60):
        counter.hit("alice")
    assert counter.hit("alice").allowed is False


def test_hits_after_61st_in_same_window_are_denied(counter: RateCounter) -> None:
    """同一ウィンドウの 62 回目以降も拒否され続けること。"""
    for _ in range(60):
        counter.hit("alice")
    for _ in range(10):
        assert counter.hit("alice").allowed is False


def test_counting_restarts_in_next_window(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """拒否された後でも次のウィンドウでは 60 回許可され 61 回目が拒否されること。"""
    for _ in range(61):
        counter.hit("alice")
    fake_clock.now = 60.0
    for _ in range(60):
        assert counter.hit("alice").allowed is True
    assert counter.hit("alice").allowed is False


def test_users_are_counted_independently(counter: RateCounter) -> None:
    """ユーザー A が上限に達して拒否されても、ユーザー B は許可されること。"""
    for _ in range(61):
        counter.hit("alice")
    assert counter.hit("alice").allowed is False
    assert counter.hit("bob").allowed is True


def test_other_user_count_is_not_affected(counter: RateCounter) -> None:
    """ユーザー B の上限が、ユーザー A のリクエストに影響されず 60 回であること。"""
    for _ in range(100):
        counter.hit("alice")
    for _ in range(60):
        assert counter.hit("bob").allowed is True
    assert counter.hit("bob").allowed is False


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (0.0, 60),
        (0.5, 60),
        (30.0, 30),
        (59.0, 1),
        (59.001, 1),
        (59.999, 1),
        (60.0, 60),
        (119.999, 1),
        (10.7, 50),
        (29.6, 31),
        (1_700_000_000.25, 40),
        (1_700_000_099.999999, 1),
        (1_700_000_050.4, 50),
        (1_700_000_050.6, 50),
    ],
    ids=[
        "0.0",
        "0.5",
        "30.0",
        "59.0",
        "59.001",
        "59.999",
        "60.0",
        "119.999",
        "remaining-49.3",
        "remaining-30.4",
        "remaining-39.75-large-epoch",
        "remaining-0.000001-large-epoch",
        "remaining-49.6-large-epoch",
        "remaining-49.4-large-epoch",
    ],
)
def test_retry_after_when_allowed(
    counter: RateCounter, fake_clock: FakeClock, now: float, expected: int
) -> None:
    """許可の場合の retry_after が、切り上げた残り秒数（最小 1）であること。"""
    fake_clock.now = now
    decision = counter.hit("alice")
    assert decision.allowed is True
    assert decision.retry_after == expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (0.0, 60),
        (0.5, 60),
        (30.0, 30),
        (59.0, 1),
        (59.001, 1),
        (59.999, 1),
        (60.0, 60),
        (119.999, 1),
        (10.7, 50),
        (29.6, 31),
        (1_700_000_000.25, 40),
        (1_700_000_099.999999, 1),
        (1_700_000_050.4, 50),
        (1_700_000_050.6, 50),
    ],
    ids=[
        "0.0",
        "0.5",
        "30.0",
        "59.0",
        "59.001",
        "59.999",
        "60.0",
        "119.999",
        "remaining-49.3",
        "remaining-30.4",
        "remaining-39.75-large-epoch",
        "remaining-0.000001-large-epoch",
        "remaining-49.6-large-epoch",
        "remaining-49.4-large-epoch",
    ],
)
def test_retry_after_when_denied(
    counter: RateCounter, fake_clock: FakeClock, now: float, expected: int
) -> None:
    """拒否の場合の retry_after が、許可の場合と同じ式の値であること。"""
    fake_clock.now = now
    for _ in range(60):
        counter.hit("alice")
    decision = counter.hit("alice")
    assert decision.allowed is False
    assert decision.retry_after == expected


def test_retry_after_is_int(counter: RateCounter, fake_clock: FakeClock) -> None:
    """retry_after が整数（int）であること。"""
    fake_clock.now = 0.5
    retry_after = counter.hit("alice").retry_after
    assert isinstance(retry_after, int)
    assert not isinstance(retry_after, bool)


def test_time_59_999_belongs_to_first_window(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """時刻 59.999 が最初のウィンドウに属し、0.0 からの数えが続くこと。"""
    for _ in range(60):
        counter.hit("alice")
    fake_clock.now = 59.999
    assert counter.hit("alice").allowed is False


def test_time_60_0_starts_next_window(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """時刻 60.0 が次のウィンドウの開始で、カウントが数え直されること。"""
    fake_clock.now = 59.999
    for _ in range(61):
        counter.hit("alice")
    fake_clock.now = 60.0
    assert counter.hit("alice").allowed is True


def test_first_hit_at_window_start_0_0_is_allowed(counter: RateCounter) -> None:
    """最初のウィンドウの最初の瞬間（0.0）の 1 回目が許可されること。"""
    assert counter.hit("alice").allowed is True


def test_first_hit_at_window_start_60_0_is_allowed(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """次のウィンドウの最初の瞬間（60.0）の 1 回目が許可されること。"""
    fake_clock.now = 60.0
    assert counter.hit("alice").allowed is True


def test_size_stays_1_after_many_windows(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """1000 ウィンドウ分呼んでも、保持するカウントが 1 件のままであること。"""
    for window in range(1000):
        fake_clock.now = window * 60.0
        counter.hit("alice")
        assert counter.size() == 1


def test_size_equals_number_of_users(counter: RateCounter) -> None:
    """複数ユーザーが呼ぶと、保持するカウントがユーザー数になること。"""
    for user in ["alice", "bob", "carol"]:
        counter.hit(user)
    assert counter.size() == 3


def test_size_is_0_before_any_hit(counter: RateCounter) -> None:
    """一度も呼ばれていないカウンターの保持数が 0 であること。"""
    assert counter.size() == 0


def test_clock_going_back_restarts_counting(
    counter: RateCounter, fake_clock: FakeClock
) -> None:
    """時計が前のウィンドウに戻ると、別のウィンドウとして 1 回目から数え直すこと。"""
    fake_clock.now = 5 * 60.0
    for _ in range(61):
        counter.hit("alice")
    assert counter.hit("alice").allowed is False
    fake_clock.now = 4 * 60.0
    assert counter.hit("alice").allowed is True
    assert counter.size() == 1


class YieldingUser(str):
    """ハッシュ計算のたびに GIL を譲る、競合の窓を開けるためのユーザー名。"""

    def __hash__(self) -> int:
        """スレッドの切り替えを促してから、通常の str と同じハッシュを返す。"""
        time.sleep(0)
        return super().__hash__()


@pytest.fixture
def short_switch_interval() -> Iterator[None]:
    """スレッドの切り替え間隔を一時的に短くし、終了後に元へ戻す。"""
    original = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(original)


@pytest.mark.usefixtures("short_switch_interval")
@pytest.mark.parametrize("repeat", range(20))
def test_concurrent_hits_are_counted_exactly(counter: RateCounter, repeat: int) -> None:
    """切り替えが起きやすくても、許可がちょうど 60 回、拒否が 40 回であること。"""
    threads = 100
    barrier = threading.Barrier(threads)

    def worker() -> bool:
        """全スレッドをそろえてから 1 回呼び、許可されたかを返す。"""
        barrier.wait()
        return counter.hit(YieldingUser("alice")).allowed

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker) for _ in range(threads)]
        results = [future.result() for future in futures]

    assert results.count(True) == 60
    assert results.count(False) == 40


def test_counters_do_not_share_state(fake_clock: FakeClock) -> None:
    """2 つの RateCounter のカウントが共有されないこと。"""
    first = RateCounter(clock=fake_clock)
    second = RateCounter(clock=fake_clock)
    for _ in range(61):
        first.hit("alice")
    assert first.hit("alice").allowed is False
    assert second.hit("alice").allowed is True
    assert second.size() == 1


def test_default_clock_can_be_used() -> None:
    """引数なしで作った RateCounter が、既定の時計で hit を呼べること。"""
    decision = RateCounter().hit("alice")
    assert decision.allowed is True
    assert 1 <= decision.retry_after <= 60

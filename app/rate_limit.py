"""ユーザーごとの固定ウィンドウ方式のレート制限カウンターを提供する。

時刻を ``WINDOW_SECONDS`` 秒ごとのウィンドウに区切り、ユーザーごとに
ウィンドウ内のリクエスト回数を数える。上限は ``RATE_LIMIT`` 回で、
超えた分は拒否する。現在時刻は差し替え可能で、カウントは排他制御される。
"""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

RATE_LIMIT = 60
WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateDecision:
    """1 回のリクエストに対するレート制限の判定結果。

    Attributes
    ----------
    allowed : bool
        リクエストが許可された場合は True、上限超過で拒否された場合は False。
    retry_after : int
        現在のウィンドウが終わるまでの残り秒数。切り上げた整数で、最小 1。
        許可された場合も同じ式で計算した値を持つ。
    """

    allowed: bool
    retry_after: int


class RateCounter:
    """ユーザーごとの固定ウィンドウ方式のリクエストカウンター。

    ユーザーごとに、最後に数えたウィンドウの番号とその回数だけを保持する。
    インスタンスごとに状態は独立しており、複数スレッドから同時に呼べる。
    """

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        """カウンターを作る。

        Parameters
        ----------
        clock : Callable[[], float]
            現在時刻（UNIX 時間の秒）を返す関数。テストで差し替えられる。
        """
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, user: str) -> RateDecision:
        """``user`` のリクエストを 1 回と数え、許可か拒否かを返す。

        同一ウィンドウの 1 回目から ``RATE_LIMIT`` 回目までは許可し、
        それ以降は拒否する。ウィンドウが変わると 1 回目から数え直す。
        ユーザー間のカウントは互いに影響しない。

        Parameters
        ----------
        user : str
            カウントの単位となるユーザー名。

        Returns
        -------
        RateDecision
            許可かどうかと、現在のウィンドウが終わるまでの残り秒数。
        """
        with self._lock:
            now = self._clock()
            window = int(now // WINDOW_SECONDS)
            last_window, count = self._counts.get(user, (window, 0))
            if last_window != window:
                count = 0
            count += 1
            self._counts[user] = (window, count)
            retry_after = max(1, math.ceil((window + 1) * WINDOW_SECONDS - now))
            return RateDecision(allowed=count <= RATE_LIMIT, retry_after=retry_after)

    def size(self) -> int:
        """保持しているカウントの数を返す。

        ユーザーごとに最後に数えたウィンドウの 1 件を保持するため、
        数えたことのあるユーザー数に等しい。

        Returns
        -------
        int
            保持しているカウントの数。
        """
        with self._lock:
            return len(self._counts)

"""時間に依存する振る舞いを検証するための、差し替え用の時計を置く。"""


class FakeClock:
    """テストから進められる、差し替え用の時計。

    Attributes
    ----------
    now : float
        現在時刻（UNIX 時間の秒）。テストが直接書き換えて時間を進める。
    """

    def __init__(self, now: float = 0.0) -> None:
        """現在時刻（UNIX 時間の秒）の初期値を設定する。

        Parameters
        ----------
        now : float, default 0.0
            時計の初期時刻（秒）。
        """
        self.now = now

    def __call__(self) -> float:
        """現在時刻を返す。

        Returns
        -------
        float
            現在時刻（UNIX 時間の秒）。
        """
        return self.now

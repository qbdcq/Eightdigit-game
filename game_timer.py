"""游戏计时状态，与 Tkinter 和界面代码无关。"""

from time import monotonic
from typing import Callable


class GameTimer:
    """支持开始、暂停、继续和重置的累计计时器。"""

    def __init__(self, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._elapsed_before = 0.0
        self._started_at: float | None = None

    @property
    def running(self) -> bool:
        return self._started_at is not None

    def elapsed_seconds(self) -> int:
        total = self._elapsed_before
        if self._started_at is not None:
            total += self._clock() - self._started_at
        return max(0, int(total))

    def start(self) -> None:
        """开始或继续计时；已运行时不重复开始。"""
        if self._started_at is None:
            self._started_at = self._clock()

    def stop(self) -> None:
        """暂停计时，并保留已经累计的时间。"""
        if self._started_at is not None:
            self._elapsed_before += self._clock() - self._started_at
            self._started_at = None

    def reset(self, elapsed_seconds: float = 0) -> None:
        """重置计时；读档时可传入已累计秒数。"""
        self._elapsed_before = max(0, float(elapsed_seconds))
        self._started_at = None

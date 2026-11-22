from datetime import datetime

from copilot_metrics.shared.kernel import Clock


class FixedClock(Clock):
    """A clock that stands still until a test moves ``current``."""

    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current

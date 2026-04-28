from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass
class RateLimitResult:
    allowed: bool
    message: str | None = None


@dataclass
class _UserUsage:
    day: date
    count: int = 0
    last_request_at: datetime | None = None


class InMemoryRateLimiter:
    def __init__(self, daily_limit: int, min_seconds_between_requests: int) -> None:
        self._daily_limit = daily_limit
        self._min_seconds_between_requests = min_seconds_between_requests
        self._usage: dict[int, _UserUsage] = {}

    def check_and_increment(self, user_id: int) -> RateLimitResult:
        now = datetime.now(UTC)
        today = now.date()
        usage = self._usage.get(user_id)

        if usage is None or usage.day != today:
            usage = _UserUsage(day=today)
            self._usage[user_id] = usage

        if usage.last_request_at is not None:
            elapsed = (now - usage.last_request_at).total_seconds()
            wait_for = self._min_seconds_between_requests - elapsed
            if wait_for > 0:
                return RateLimitResult(
                    allowed=False,
                    message=f"Слишком часто. Попробуйте снова через {int(wait_for) + 1} сек.",
                )

        if usage.count >= self._daily_limit:
            return RateLimitResult(
                allowed=False,
                message=(
                    "Дневной лимит запросов исчерпан. "
                    "Попробуйте снова завтра или увеличьте USER_DAILY_LIMIT."
                ),
            )

        usage.count += 1
        usage.last_request_at = now
        return RateLimitResult(allowed=True)

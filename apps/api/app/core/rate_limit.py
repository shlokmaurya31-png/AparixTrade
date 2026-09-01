"""A real, working fixed-window rate limiter — Tier 1 §42. In-process only:
counters live in a plain dict, not shared across worker processes or
instances. Consistent with the rest of this app's architecture (one
asyncio process, SQLite, no Redis/shared cache — see docs/ARCHITECTURE.md
§9), not a shortcut around building something more scalable.

Known, documented limitation (same "correct at today's scale, not
infinitely" pattern as domains/admin/data_quality.py's
check_candle_integrity() full-table-scan docstring): `_hits` grows one key
per distinct client seen, forever — nothing ever evicts a key for a client
that stopped making requests. Fine for this app's actual usage (a local,
single/few-user demo); a real multi-tenant deployment would need a
TTL-evicting store instead.
"""

import time
from collections import defaultdict


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds). Records the hit only
        when allowed — a request that gets rejected doesn't itself count
        against the next window."""
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.pop(0)

        if len(hits) >= self.max_requests:
            retry_after = hits[0] + self.window_seconds - now
            return False, max(retry_after, 0.0)

        hits.append(now)
        return True, 0.0

"""Per-session conversation memory in Redis.

Each session is a Redis list of JSON messages trimmed to the last ``max_turns`` exchanges
and refreshed with a TTL on every write, so abandoned sessions expire on their own.
"""

from __future__ import annotations

import json
from typing import Any


class SessionMemory:
    def __init__(self, redis, max_turns: int = 8, ttl_seconds: int = 3600) -> None:
        self._redis = redis
        self._max_messages = max_turns * 2
        self._ttl = ttl_seconds

    @staticmethod
    def key(session_id: str) -> str:
        return f"gator:session:{session_id}"

    async def history(self, session_id: str) -> list[dict[str, Any]]:
        raw = await self._redis.lrange(self.key(session_id), 0, -1)
        return [json.loads(item) for item in raw]

    async def append(self, session_id: str, *messages: dict[str, Any]) -> None:
        if not messages:
            return
        key = self.key(session_id)
        pipe = self._redis.pipeline()
        pipe.rpush(key, *(json.dumps(m) for m in messages))
        pipe.ltrim(key, -self._max_messages, -1)
        pipe.expire(key, self._ttl)
        await pipe.execute()

    async def clear(self, session_id: str) -> None:
        await self._redis.delete(self.key(session_id))

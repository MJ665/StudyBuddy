import json
from typing import Any, List, Optional

import httpx
from config import settings

UPSTASH_URL = settings.UPSTASH_REDIS_REST_URL
UPSTASH_TOKEN = settings.UPSTASH_REDIS_REST_TOKEN


class RedisService:
    def __init__(self):
        self.enabled = bool(UPSTASH_URL and UPSTASH_TOKEN)
        self.headers = (
            {"Authorization": f"Bearer {UPSTASH_TOKEN}"} if self.enabled else {}
        )

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{UPSTASH_URL}/get/{key}", headers=self.headers, timeout=2.0
                )
                if res.status_code == 200:
                    data = res.json()
                    result = data.get("result")
                    if result is not None:
                        # FIX #10: handle plain strings that are not JSON-encoded
                        try:
                            return json.loads(result)
                        except (json.JSONDecodeError, TypeError):
                            return result
        except Exception as e:
            print(f"Redis GET error: {e}")
        return None

    async def set(self, key: str, value: Any, ex: int = 3600, nx: bool = False):
        if not self.enabled:
            return

        def datetime_handler(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {obj.__class__.__name__} is not JSON serializable"
            )

        try:
            async with httpx.AsyncClient() as client:
                payload = json.dumps(value, default=datetime_handler)
                url = f"{UPSTASH_URL}/set/{key}"
                params = []
                if ex:
                    params.append(f"EX={ex}")
                if nx:
                    params.append("NX")
                if params:
                    url += "?" + "&".join(params)
                res = await client.post(
                    url, headers=self.headers, content=payload, timeout=2.0
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("result") == "OK"
                return False
        except Exception as e:
            print(f"Redis SET error: {e}")
            return False

    async def delete(self, key: str):
        if not self.enabled:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.get(
                    f"{UPSTASH_URL}/del/{key}", headers=self.headers, timeout=2.0
                )
        except Exception as e:
            print(f"Redis DEL error: {e}")

    async def sadd(self, key: str, member: str):
        if not self.enabled:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.get(
                    f"{UPSTASH_URL}/sadd/{key}/{member}",
                    headers=self.headers,
                    timeout=2.0,
                )
        except Exception as e:
            print(f"Redis SADD error: {e}")

    async def smembers(self, key: str) -> List[str]:
        if not self.enabled:
            return []
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{UPSTASH_URL}/smembers/{key}", headers=self.headers, timeout=2.0
                )
                if res.status_code == 200:
                    return res.json().get("result", [])
        except Exception as e:
            print(f"Redis SMEMBERS error: {e}")
        return []

    async def srem(self, key: str, member: str):
        if not self.enabled:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.get(
                    f"{UPSTASH_URL}/srem/{key}/{member}",
                    headers=self.headers,
                    timeout=2.0,
                )
        except Exception as e:
            print(f"Redis SREM error: {e}")

    async def list_keys(self, pattern: str) -> List[str]:
        """List all keys matching a glob pattern via SCAN."""
        if not self.enabled:
            return []
        keys = []
        cursor = 0
        try:
            async with httpx.AsyncClient() as client:
                while True:
                    res = await client.get(
                        f"{UPSTASH_URL}/scan/{cursor}",
                        params={"match": pattern, "count": 100},
                        headers=self.headers,
                        timeout=3.0,
                    )
                    if res.status_code == 200:
                        data = res.json().get("result", [0, []])
                        cursor = int(data[0])
                        keys.extend(data[1])
                        if cursor == 0:
                            break
                    else:
                        break
        except Exception as e:
            print(f"Redis SCAN error: {e}")
        return keys

    async def ping(self) -> bool:
        """Returns True if the Redis connection is healthy."""
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{UPSTASH_URL}/ping", headers=self.headers, timeout=2.0
                )
                return res.status_code == 200
        except Exception:
            return False

    async def incr(self, key: str) -> int:
        """Increments the integer value of a key by one."""
        if not self.enabled:
            return 0
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{UPSTASH_URL}/incr/{key}", headers=self.headers, timeout=2.0
                )
                if res.status_code == 200:
                    return int(res.json().get("result", 0))
        except Exception as e:
            print(f"Redis INCR error: {e}")
        return 0

    async def decr(self, key: str) -> int:
        """Decrements the integer value of a key by one."""
        if not self.enabled:
            return 0
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{UPSTASH_URL}/decr/{key}", headers=self.headers, timeout=2.0
                )
                if res.status_code == 200:
                    return int(res.json().get("result", 0))
        except Exception as e:
            print(f"Redis DECR error: {e}")
        return 0


redis_client = RedisService()

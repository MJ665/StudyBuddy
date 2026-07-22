import inspect

from fastapi.concurrency import run_in_threadpool
import functools
import logging
from typing import Callable

from services.redis_service import redis_client

logger = logging.getLogger("cache")


class CacheManager:
    @staticmethod
    def get_key(*args, **kwargs) -> str:
        """Generates a stable cache key by filtering out non-serializable objects."""
        # Filter out 'db', 'current_user', 'self', 'cls' and other context objects
        filtered_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["db", "current_user", "self", "cls", "refresh"]
        }
        # Filter non-primitive args (like Session objects)
        filtered_args = [
            a for a in args if isinstance(a, (str, int, float, bool, type(None)))
        ]

        arg_str = ":".join(map(str, filtered_args))
        kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(filtered_kwargs.items()))
        return f"{arg_str}|{kwarg_str}"

    @staticmethod
    def cached(prefix: str, ttl: int = 300):
        """
        Decorator for caching async function results in Upstash Redis.
        Default TTL: 5 minutes.
        Supports bypassing cache if 'refresh=True' is passed in kwargs.
        """

        def decorator(func: Callable):
            # The wrapped endpoint may be `def` OR `async def`. FastAPI allows both,
            # and several handlers are deliberately sync so FastAPI threadpools
            # them. Blindly `await func(...)` raised
            # "object dict can't be used in 'await' expression" and 500'd every
            # sync handler that used this decorator.
            is_async = inspect.iscoroutinefunction(func)

            async def _invoke(*a, **kw):
                if is_async:
                    return await func(*a, **kw)
                # keep sync handlers off the event loop, as FastAPI would
                return await run_in_threadpool(func, *a, **kw)

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                refresh = kwargs.get("refresh", False)

                if not redis_client.enabled:
                    return await _invoke(*args, **kwargs)

                # Filter out non-serializable or control kwargs
                cache_kwargs = {
                    k: v for k, v in kwargs.items() if k not in ["db", "refresh"]
                }

                key = f"{prefix}:{CacheManager.get_key(*args, **cache_kwargs)}"

                if not refresh:
                    try:
                        cached_data = await redis_client.get(key)
                        if cached_data is not None:
                            logger.info(f"Cache Hit: {key}")
                            return cached_data
                    except Exception as e:
                        logger.warning(f"Cache Read Failure for {key}: {e}")

                result = await _invoke(*args, **kwargs)

                try:
                    await redis_client.set(key, result, ex=ttl)
                    # STRAT-CACHE-V4: Track this key for O(1) invalidation (Track-and-Clear)
                    await redis_client.sadd(f"tracked_keys:{prefix}", key)
                    logger.info(f"Cache Miss/Refresh: {key} (Stored for {ttl}s)")
                except Exception as e:
                    logger.warning(f"Cache Write Failure for {key}: {e}")

                return result

            return wrapper

        return decorator

    @staticmethod
    async def invalidate(prefix: str):
        """
        STRAT-CACHE-V4: Optimized Track-and-Clear invalidation.
        Handles both global prefixes (e.g. "global_stats") and scoped prefixes (e.g. "user_vectors:123").
        """
        if not redis_client.enabled:
            return

        try:
            # 1. Determine the root tracking prefix (e.g., "user_vectors" from "user_vectors:123")
            root_prefix = prefix.split(":")[0]
            tracked_set_key = f"tracked_keys:{root_prefix}"

            # 2. Fetch all keys tracked under this root
            all_tracked_keys = await redis_client.smembers(tracked_set_key)

            # 3. Filter keys that match the full scoped prefix
            # If prefix is "user_vectors:123", we match "user_vectors:123|..."
            target_keys = [k for k in all_tracked_keys if k.startswith(prefix)]

            # 4. Fallback to SCAN if no tracked keys found (legacy or external keys)
            if not target_keys:
                pattern = f"{prefix}*"
                target_keys = await redis_client.list_keys(pattern)

            # 5. Batch deletion
            target_keys_set = set(target_keys)
            if prefix in target_keys_set or True:  # Ensure direct prefix is also considered
                target_keys_set.add(prefix)

            for key in target_keys_set:
                await redis_client.delete(key)
                # Remove from tracking set to keep it clean
                await redis_client.srem(tracked_set_key, key)

            # 6. If we cleared everything for a root, delete the set
            if not await redis_client.smembers(tracked_set_key):
                await redis_client.delete(tracked_set_key)

            if target_keys:
                logger.info(
                    f"Cache invalidated {len(target_keys)} key(s) for prefix '{prefix}'."
                )
        except Exception as e:
            logger.warning(f"Cache Invalidation Error for prefix '{prefix}': {e}")


cache_manager = CacheManager()

import asyncio
import os
import sys

import httpx

# Add parent directory to path to access local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from dotenv import load_dotenv  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")


async def clear_redis():
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        print("⚠️ Upstash Redis not configured. Skipping cache purge.")
        return

    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}

    try:
        async with httpx.AsyncClient() as client:
            # Upstash REST supports 'FLUSHDB' via GET or POST
            res = await client.get(
                f"{UPSTASH_URL}/flushdb", headers=headers, timeout=5.0
            )
            if res.status_code == 200:
                print(f"✅ Redis Cache Purged successfully (Upstash: {UPSTASH_URL})")
            else:
                print(
                    f"❌ Failed to clear Redis. Status: {res.status_code}, Body: {res.text}"
                )
    except Exception as e:
        print(f"❌ Error connecting to Upstash: {e}")


if __name__ == "__main__":
    asyncio.run(clear_redis())

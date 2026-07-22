import hashlib
import json
import logging
import time
from typing import Dict, List, Optional

import httpx
from config import settings
from google import genai
from services.redis_service import redis_client

logger = logging.getLogger("vector_service")


class VectorService:
    def __init__(self):
        self.url = settings.UPSTASH_VECTOR_REST_URL
        self.token = settings.UPSTASH_VECTOR_REST_TOKEN
        self.enabled = bool(self.url and self.token)

        if self.enabled and settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_id = "gemini-embedding-2"
        else:
            self.client = None
            logger.warning("Vector service disabled: Credentials missing.")

    async def embed_text(self, text: str) -> List[float]:
        """
        Embed text using Google Generative AI. Caches results in Redis.
        """
        if not self.client:
            return []

        # Cache lookup
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = f"emb:v2:{text_hash}"

        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache lookup failed for embedding: {e}")

        # API Call
        try:
            response = await self.client.aio.models.embed_content(
                model=self.model_id, contents=text
            )

            if not response.embeddings or not response.embeddings[0].values:
                return []

            vector = response.embeddings[0].values

            # Cache for 24h
            try:
                await redis_client.set(cache_key, json.dumps(vector), ex=86400)
            except Exception:
                pass

            return vector
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

    async def upsert_chat_memory(
        self,
        session_id: str,
        user_id: int,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        """
        Upserts a chat message into the vector store.
        """
        if not self.enabled:
            return

        vector = await self.embed_text(content)
        if not vector:
            return

        timestamp_ms = int(time.time() * 1000)
        vector_id = f"{session_id}:{timestamp_ms}"

        meta = metadata or {}
        meta.update(
            {
                "user_id": user_id,
                "role": role,
                "content": content[:1000],  # Cap for metadata storage
                "session_id": session_id,
                "timestamp": timestamp_ms,
            }
        )

        payload = {"id": vector_id, "vector": vector, "metadata": meta}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/upsert",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=payload,
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Vector upsert failed: {e}")
            return False

    async def upsert_user_performance_vector(self, user_id: int, metrics: Dict):
        """
        Stores the 30-metric performance profile as a high-dimensional vector.
        """
        if not self.enabled:
            return

        # Extract raw values in deterministic order (m01 to m30)
        vector_keys = sorted(
            [k for k in metrics.keys() if k.startswith("m") and k[1:3].isdigit()]
        )
        vector = [float(metrics[k].get("raw", 0)) for k in vector_keys]

        # Ensure we have a fixed dimension matching the 3072-dim index
        if len(vector) < 3072:
            vector.extend([0.0] * (3072 - len(vector)))
        elif len(vector) > 3072:
            vector = vector[:3072]

        payload = {
            "id": f"perf:{user_id}",
            "vector": vector,
            "metadata": {
                "user_id": user_id,
                "type": "performance_profile",
                "updated_at": int(time.time()),
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/upsert",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=payload,
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Performance vector upsert failed: {e}")
            return False

    async def get_similar_learners(self, user_id: int, k: int = 5) -> List[int]:
        """
        Finds top-k similar learners based on performance vectors.
        """
        if not self.enabled:
            return []

        try:
            # First get the vector for the user
            async with httpx.AsyncClient() as client:
                fetch_res = await client.post(
                    f"{self.url}/fetch",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"ids": [f"perf:{user_id}"]},
                )
                fetch_res.raise_for_status()
                data = fetch_res.json()
                if not data or not data.get("vectors") or not data["vectors"][0]:
                    return []

                target_vector = data["vectors"][0]["vector"]

                # Now query for similar
                query_res = await client.post(
                    f"{self.url}/query",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "vector": target_vector,
                        "topK": k + 1,  # +1 to exclude self
                        "includeMetadata": True,
                    },
                )
                query_res.raise_for_status()
                matches = query_res.json().get("result", [])

                similar_ids = []
                for match in matches:
                    uid = match.get("metadata", {}).get("user_id")
                    if uid and int(uid) != user_id:
                        similar_ids.append(int(uid))

                return similar_ids[:k]
        except Exception as e:
            logger.error(f"Similar learner lookup failed: {e}")
            return []

    async def retrieve_relevant_context(
        self, user_id: int, query: str, top_k: int = 5
    ) -> List[dict]:
        """
        Performs vector similarity search for relevant past interactions.
        """
        if not self.enabled:
            return []

        vector = await self.embed_text(query)
        if not vector:
            return []

        payload = {
            "vector": vector,
            "topK": top_k,
            "includeMetadata": True,
            "filter": f"user_id = {user_id}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/query",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=payload,
                )
                response.raise_for_status()
                results = response.json().get("result", [])

                return [
                    {
                        "content": r.get("metadata", {}).get("content", ""),
                        "role": r.get("metadata", {}).get("role", ""),
                        "score": r.get("score", 0),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            return []

    async def clear_session_memory(self, session_id: str):
        """
        Deletes all vectors for a specific session.
        Note: Upstash Vector doesn't support prefix delete via REST directly easily without scanning.
        For now, we'll implement this as a logical separation in queries.
        """
        pass

    async def get_user_memory_summary(self, user_id: int) -> List[dict]:
        """
        Returns recent interactions for a user.
        """
        # In a real implementation, we might query the vector store for recent entries
        # Or query the DB. For context augmentation, similarity search is better.
        return []


vector_service = VectorService()

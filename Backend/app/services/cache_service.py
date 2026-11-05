"""
In-Memory Analytical Query Cache Service.
Provides high-performance caching for repetitive analytical questions, eliminating redundant LLM API calls and DuckDB queries.
"""

import hashlib
import time
from typing import Any, Dict, Optional
from threading import Lock

from app.services.logger_service import logger


class QueryCache:
    def __init__(self, max_entries: int = 200, default_ttl: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._lock = Lock()

    def _normalize(self, text: str) -> str:
        """Normalizes question string for stable cache matching."""
        if not text:
            return ""
        # Lowercase, strip whitespace, remove common trailing punctuation
        cleaned = text.lower().strip().rstrip("?.!").strip()
        # Collapse multiple spaces into single space
        return " ".join(cleaned.split())

    def _generate_key(self, dataset_id: str, question: str) -> str:
        """Generates deterministic SHA-256 hash key."""
        norm_q = self._normalize(question)
        raw_key = f"{dataset_id}:{norm_q}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, dataset_id: str, question: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached response if present and unexpired."""
        key = self._generate_key(dataset_id, question)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                logger.info(f"[CACHE MISS] question='{question[:40]}...' (dataset={dataset_id})")
                return None

            entry = self._cache[key]
            now = time.time()
            # Check expiration
            if now - entry["cached_at"] > entry["ttl"]:
                del self._cache[key]
                self._misses += 1
                logger.info(f"[CACHE EXPIRED] question='{question[:40]}...'")
                return None

            entry["hits"] += 1
            self._hits += 1
            logger.info(f"[CACHE HIT #{entry['hits']}] question='{question[:40]}...' (served in <5ms)")

            cached_data = dict(entry["data"])
            cached_data["cached"] = True
            cached_data["cache_hit_count"] = entry["hits"]
            return cached_data

    def set(self, dataset_id: str, question: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Stores analysis result in cache with TTL and LRU-style eviction."""
        key = self._generate_key(dataset_id, question)
        ttl_seconds = ttl if ttl is not None else self._default_ttl

        with self._lock:
            # Simple eviction if cache is full: remove oldest entry
            if len(self._cache) >= self._max_entries and key not in self._cache:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["cached_at"])
                del self._cache[oldest_key]

            self._cache[key] = {
                "dataset_id": dataset_id,
                "question": question,
                "data": data,
                "cached_at": time.time(),
                "ttl": ttl_seconds,
                "hits": 0,
            }
            logger.info(f"[CACHE STORED] question='{question[:40]}...' (ttl={ttl_seconds}s)")

    def clear(self) -> None:
        """Empties the cache."""
        with self._lock:
            self._cache.clear()
            logger.info("[CACHE CLEARED] All cached analytical results purged.")

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry and hit ratio."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = round((self._hits / total_requests * 100), 1) if total_requests > 0 else 0.0
            return {
                "total_cached_queries": len(self._cache),
                "cache_hits": self._hits,
                "cache_misses": self._misses,
                "hit_ratio_percent": hit_ratio,
            }


# Global singleton instance
query_cache = QueryCache()

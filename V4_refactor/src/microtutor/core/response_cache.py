"""
Response caching system for LLM responses.

This module provides intelligent caching of LLM responses to avoid
repeated expensive API calls for similar queries.
"""

import hashlib
import json
import logging
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import pickle
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """Represents a cached LLM response."""
    content: str
    model: str
    prompt_hash: str
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
        if self.metadata is None:
            self.metadata = {}


class ResponseCache:
    """Intelligent response cache for LLM responses."""
    
    def __init__(
        self,
        cache_dir: str = "data/cache",
        max_size: int = 1000,
        ttl_hours: int = 24,
        similarity_threshold: float = 0.8
    ):
        """Initialize response cache.
        
        Args:
            cache_dir: Directory to store cache files
            max_size: Maximum number of cached responses
            ttl_hours: Time-to-live for cached responses in hours
            similarity_threshold: Threshold for considering prompts similar
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self.similarity_threshold = similarity_threshold
        
        # In-memory cache for fast access
        self._cache: Dict[str, CachedResponse] = {}
        self._access_times: Dict[str, float] = {}
        
        # Load existing cache
        self._load_cache()
        
        logger.info(f"ResponseCache initialized: {len(self._cache)} cached responses")
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            cache_file = self.cache_dir / "response_cache.pkl"
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self._cache = data.get('cache', {})
                    self._access_times = data.get('access_times', {})
                logger.info(f"Loaded {len(self._cache)} cached responses from disk")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self._cache = {}
            self._access_times = {}
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            cache_file = self.cache_dir / "response_cache.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'cache': self._cache,
                    'access_times': self._access_times
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _generate_prompt_hash(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        tools: Optional[list] = None
    ) -> str:
        """Generate hash for prompt combination.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Model name
            tools: Optional tools list
            
        Returns:
            Hash string for the prompt combination
        """
        # Normalize prompts for better matching
        normalized_system = system_prompt.strip().lower()
        normalized_user = user_prompt.strip().lower()
        
        # Create hash input
        hash_input = {
            "system": normalized_system,
            "user": normalized_user,
            "model": model,
            "tools": sorted(tools) if tools else []
        }
        
        # Generate hash
        hash_string = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def _is_expired(self, cached_response: CachedResponse) -> bool:
        """Check if cached response is expired.
        
        Args:
            cached_response: Cached response to check
            
        Returns:
            True if expired, False otherwise
        """
        expiry_time = cached_response.created_at + timedelta(hours=self.ttl_hours)
        return datetime.utcnow() > expiry_time
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        expired_keys = []
        for key, response in self._cache.items():
            if self._is_expired(response):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries if cache is full."""
        if len(self._cache) < self.max_size:
            return
        
        # Sort by access time (oldest first)
        sorted_items = sorted(
            self._access_times.items(),
            key=lambda x: x[1]
        )
        
        # Remove oldest entries
        to_remove = len(self._cache) - self.max_size + 1
        for key, _ in sorted_items[:to_remove]:
            if key in self._cache:
                del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
        
        logger.info(f"Evicted {to_remove} LRU cache entries")
    
    def get(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        tools: Optional[list] = None
    ) -> Optional[str]:
        """Get cached response if available.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Model name
            tools: Optional tools list
            
        Returns:
            Cached response content or None if not found
        """
        prompt_hash = self._generate_prompt_hash(
            system_prompt, user_prompt, model, tools
        )
        
        if prompt_hash in self._cache:
            cached_response = self._cache[prompt_hash]
            
            # Check if expired
            if self._is_expired(cached_response):
                del self._cache[prompt_hash]
                if prompt_hash in self._access_times:
                    del self._access_times[prompt_hash]
                return None
            
            # Update access info
            cached_response.access_count += 1
            cached_response.last_accessed = datetime.utcnow()
            self._access_times[prompt_hash] = time.time()
            
            logger.debug(f"Cache hit for prompt hash: {prompt_hash[:8]}...")
            return cached_response.content
        
        logger.debug(f"Cache miss for prompt hash: {prompt_hash[:8]}...")
        return None
    
    def put(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        response_content: str,
        tools: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Cache a response.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Model name
            response_content: Response content to cache
            tools: Optional tools list
            metadata: Optional metadata
        """
        prompt_hash = self._generate_prompt_hash(
            system_prompt, user_prompt, model, tools
        )
        
        # Clean up expired entries first
        self._cleanup_expired()
        
        # Evict LRU if needed
        self._evict_lru()
        
        # Create cached response
        cached_response = CachedResponse(
            content=response_content,
            model=model,
            prompt_hash=prompt_hash,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Store in cache
        self._cache[prompt_hash] = cached_response
        self._access_times[prompt_hash] = time.time()
        
        # Save to disk periodically
        if len(self._cache) % 10 == 0:
            self._save_cache()
        
        logger.debug(f"Cached response for prompt hash: {prompt_hash[:8]}...")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_responses = len(self._cache)
        total_accesses = sum(response.access_count for response in self._cache.values())
        
        # Calculate age distribution
        now = datetime.utcnow()
        age_distribution = {
            "0-1h": 0,
            "1-6h": 0,
            "6-24h": 0,
            "24h+": 0
        }
        
        for response in self._cache.values():
            age_hours = (now - response.created_at).total_seconds() / 3600
            if age_hours < 1:
                age_distribution["0-1h"] += 1
            elif age_hours < 6:
                age_distribution["1-6h"] += 1
            elif age_hours < 24:
                age_distribution["6-24h"] += 1
            else:
                age_distribution["24h+"] += 1
        
        return {
            "total_responses": total_responses,
            "total_accesses": total_accesses,
            "average_accesses_per_response": total_accesses / total_responses if total_responses > 0 else 0,
            "age_distribution": age_distribution,
            "cache_hit_rate": "N/A",  # Would need to track hits/misses
            "max_size": self.max_size,
            "ttl_hours": self.ttl_hours
        }
    
    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        self._access_times.clear()
        self._save_cache()
        logger.info("Cache cleared")
    
    def cleanup(self) -> None:
        """Clean up expired entries and save cache."""
        self._cleanup_expired()
        self._save_cache()


# Global cache instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get the global response cache instance."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache


def cached_llm_call(
    system_prompt: str,
    user_prompt: str,
    model: str,
    tools: Optional[list] = None,
    cache_ttl_hours: int = 24
) -> str:
    """Make a cached LLM call.
    
    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        model: Model name
        tools: Optional tools list
        cache_ttl_hours: Cache TTL in hours
        
    Returns:
        LLM response content
    """
    cache = get_response_cache()
    
    # Try to get from cache first
    cached_response = cache.get(system_prompt, user_prompt, model, tools)
    if cached_response:
        logger.info("Using cached LLM response")
        return cached_response
    
    # Make actual LLM call
    logger.info("Making fresh LLM call")
    from microtutor.core.llm_router import chat_complete
    
    response_content = chat_complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        tools=tools
    )
    
    # Cache the response
    cache.put(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        response_content=response_content,
        tools=tools,
        metadata={
            "cached_at": datetime.utcnow().isoformat(),
            "ttl_hours": cache_ttl_hours
        }
    )
    
    return response_content

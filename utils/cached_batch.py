
from fastapi import APIRouter
from typing import Optional
import logging
from datetime import datetime, timedelta
import hashlib

router = APIRouter()
logging.basicConfig(level=logging.INFO)


def generate_cache_key(type_filter: Optional[str], page: int, page_size: int, image_quality: int, max_image_width: Optional[int]) -> str:
    """Generate a cache key based on query parameters"""
    params = f"{type_filter}_{page}_{page_size}_{image_quality}_{max_image_width}"
    return hashlib.md5(params.encode()).hexdigest()

async def get_cached_batch(cache_key: str, cache_collection=None) -> Optional[dict]:
    """Get cached batch from MongoDB cache collection"""
    try:
        if cache_collection is None:
            return None
        
        cached = await cache_collection.find_one({
            "cache_key": cache_key,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if cached:
            logging.info(f"Cache hit for key: {cache_key}")
            return cached.get("data")
        
        return None
    except Exception as e:
        logging.warning(f"Cache retrieval error: {e}")
        return None

async def set_cached_batch(cache_key: str, data: dict, ttl_hours: int = 24, cache_collection=None):
    """Cache batch data in MongoDB with TTL"""
    try:
        if cache_collection is None:
            return
        
        await cache_collection.replace_one(
            {"cache_key": cache_key},
            {
                "cache_key": cache_key,
                "data": data,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=ttl_hours)
            },
            upsert=True
        )
        logging.info(f"Cached batch with key: {cache_key}")
    except Exception as e:
        logging.warning(f"Cache storage error: {e}")
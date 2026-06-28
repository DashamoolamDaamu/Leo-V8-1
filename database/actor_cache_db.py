# database/actor_cache_db.py
# Caches actor/director filmography lookups to reduce IMDb API calls.

import logging
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

_client = AsyncIOMotorClient(DATABASE_URI)
_db     = _client[DATABASE_NAME]
_col    = _db["actor_cache"]

CACHE_TTL_DAYS = 7


async def ensure_indexes():
    try:
        await _col.create_index("name_key", unique=True)
        await _col.create_index("cached_at")
    except Exception as e:
        logger.debug(f"[ActorCache] index: {e}")


async def get_actor_cache(name: str) -> dict | None:
    key = name.lower().strip()
    try:
        doc = await _col.find_one({"name_key": key})
        if not doc:
            return None
        if datetime.now() - doc.get("cached_at", datetime.min) > timedelta(days=CACHE_TTL_DAYS):
            return None
        return doc
    except Exception:
        return None


async def store_actor_cache(name: str, data: dict):
    key = name.lower().strip()
    try:
        await _col.update_one(
            {"name_key": key},
            {"$set": {**data, "name_key": key, "cached_at": datetime.now()}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[ActorCache] store: {e}")

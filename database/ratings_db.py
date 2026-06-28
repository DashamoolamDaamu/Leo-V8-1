# database/ratings_db.py
# Stores: movie ratings (per user), search/view counts for trending.
# Two collections: movie_ratings, search_counts — never touches existing collections.

import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

_client = AsyncIOMotorClient(DATABASE_URI)
_db     = _client[DATABASE_NAME]

_ratings   = _db["movie_ratings"]    # {imdb_id, user_id, vote, ts}
_counts    = _db["search_counts"]    # {query_key, searches, views, ts}


async def ensure_indexes():
    try:
        await _ratings.create_index([("imdb_id", 1), ("user_id", 1)], unique=True)
        await _ratings.create_index("imdb_id")
        await _counts.create_index("query_key", unique=True)
        await _counts.create_index("searches")
    except Exception as e:
        logger.debug(f"[RatingsDB] index: {e}")


# ── Ratings ───────────────────────────────────────────────────────────────────

async def cast_vote(imdb_id: str, user_id: int, vote: str):
    """vote: 'good' | 'avg' | 'bad'. Upserts so user can change vote."""
    await _ratings.update_one(
        {"imdb_id": imdb_id, "user_id": user_id},
        {"$set": {"vote": vote, "ts": datetime.now()}},
        upsert=True,
    )


async def get_rating_summary(imdb_id: str) -> dict:
    """Returns {good, avg, bad, total, score}."""
    pipeline = [
        {"$match": {"imdb_id": imdb_id}},
        {"$group": {"_id": "$vote", "count": {"$sum": 1}}},
    ]
    cursor = _ratings.aggregate(pipeline)
    docs   = await cursor.to_list(length=10)
    d = {r["_id"]: r["count"] for r in docs}
    good, avg, bad = d.get("good", 0), d.get("avg", 0), d.get("bad", 0)
    total = good + avg + bad
    score = round((good * 5 + avg * 3 + bad * 1) / total, 1) if total else 0.0
    return {"good": good, "avg": avg, "bad": bad, "total": total, "score": score}


# ── Trending / Search counts ──────────────────────────────────────────────────

async def inc_search(query_key: str):
    await _counts.update_one(
        {"query_key": query_key.lower().strip()[:80]},
        {"$inc": {"searches": 1}, "$set": {"ts": datetime.now()}},
        upsert=True,
    )


async def inc_view(query_key: str):
    await _counts.update_one(
        {"query_key": query_key.lower().strip()[:80]},
        {"$inc": {"views": 1}, "$set": {"ts": datetime.now()}},
        upsert=True,
    )


async def get_trending(limit: int = 20) -> list[dict]:
    """Return top trending query_keys sorted by search + view count."""
    pipeline = [
        {"$addFields": {"score": {"$add": [{"$ifNull": ["$searches", 0]},
                                            {"$ifNull": ["$views", 0]}]}}},
        {"$sort": {"score": -1}},
        {"$limit": limit},
        {"$project": {"query_key": 1, "searches": 1, "views": 1, "score": 1}},
    ]
    cursor = _counts.aggregate(pipeline)
    return await cursor.to_list(length=limit)


async def get_top_rated(limit: int = 20) -> list[dict]:
    """Return top imdb_ids by rating score."""
    pipeline = [
        {"$group": {
            "_id":  "$imdb_id",
            "good": {"$sum": {"$cond": [{"$eq": ["$vote", "good"]}, 1, 0]}},
            "avg":  {"$sum": {"$cond": [{"$eq": ["$vote", "avg"]},  1, 0]}},
            "bad":  {"$sum": {"$cond": [{"$eq": ["$vote", "bad"]},  1, 0]}},
            "total": {"$sum": 1},
        }},
        {"$match": {"total": {"$gte": 3}}},          # min 3 votes
        {"$addFields": {"score": {
            "$divide": [
                {"$add": [
                    {"$multiply": ["$good", 5]},
                    {"$multiply": ["$avg",  3]},
                    {"$multiply": ["$bad",  1]},
                ]},
                "$total"
            ]
        }}},
        {"$sort": {"score": -1}},
        {"$limit": limit},
    ]
    cursor = _ratings.aggregate(pipeline)
    return await cursor.to_list(length=limit)

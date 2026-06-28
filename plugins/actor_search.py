# plugins/actor_search.py
# Actor / Director guided discovery.
# Uses the same IMDb REST API as the existing bot (mn-api-imdb.vercel.app).
# Completely independent — never touches auto_filter.

import asyncio
import logging
import math

from pyrogram import Client, filters, enums
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.actor_cache_db import (
    ensure_indexes as ac_ensure,
    get_actor_cache,
    store_actor_cache,
)
from database.ia_filterdb import get_search_results
from database.ratings_db    import inc_view
from plugins.user_states     import clear_state, get_state, set_state
from utils import get_size, get_settings, search_imdb_async, get_poster

logger = logging.getLogger(__name__)

FILES_PER_PAGE = 10

# ── In-memory actor result store ──────────────────────────────────────────────
# Key: f"actor_{uid}_{slug}"   Value: list of file objects
ACTOR_RESULTS: dict = {}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    """Short lowercase key safe for callback data (max 20 chars)."""
    return name.lower().replace(" ", "_")[:20]


def _build_file_buttons(files: list, settings: dict) -> list:
    pre = "filep" if settings.get("file_secure") else "file"
    if settings.get("button"):
        return [[InlineKeyboardButton(
            f"📂[{get_size(f.file_size)}]--{f.file_name}",
            callback_data=f"{pre}#{f.file_id}")] for f in files]
    return [[
        InlineKeyboardButton(f.file_name, callback_data=f"{pre}#{f.file_id}"),
        InlineKeyboardButton(get_size(f.file_size), callback_data=f"{pre}#{f.file_id}"),
    ] for f in files]


def _build_pagination(uid: int, slug: str, offset: int, total: int) -> list:
    page  = math.ceil(offset / FILES_PER_PAGE) if offset else 0
    pages = max(math.ceil(total / FILES_PER_PAGE), 1)
    row   = []
    if offset > 0:
        row.append(InlineKeyboardButton(
            "◀ Prev", callback_data=f"acnxt_{uid}_{slug}_{max(offset - FILES_PER_PAGE, 0)}"))
    row.append(InlineKeyboardButton(f"📃 {page + 1} / {pages}", callback_data="pages"))
    if offset + FILES_PER_PAGE < total:
        row.append(InlineKeyboardButton(
            "Next ▶", callback_data=f"acnxt_{uid}_{slug}_{offset + FILES_PER_PAGE}"))
    return row


async def _fetch_actor_movies(actor_name: str) -> list:
    """
    Search all indexed files whose names match movies in the actor's filmography.
    Uses: IMDb search → movie titles → MongoDB full-text search per title.
    """
    seen: dict = {}

    # ── Try cache first ───────────────────────────────────────────────────────
    cached = await get_actor_cache(actor_name)
    movie_titles = cached.get("titles", []) if cached else []

    # ── If no cache, fetch from IMDb ──────────────────────────────────────────
    if not movie_titles:
        for page in range(1, 4):
            data = await search_imdb_async(actor_name, page=page)
            results = data.get("results", [])
            if not results:
                break
            for m in results:
                title = m.get("Title") or ""
                if title and m.get("Type") in ("movie", "series", "tvseries"):
                    movie_titles.append(title)

        movie_titles = list(dict.fromkeys(movie_titles))[:60]
        await store_actor_cache(actor_name, {"titles": movie_titles})

    # ── MongoDB match ─────────────────────────────────────────────────────────
    for title in movie_titles[:50]:
        try:
            files, _, _, _ = await get_search_results(
                title, offset=0, max_results=20, filter=True, fast=True, return_time=True)
            for f in files:
                if actor_name.lower().split()[0] in (f.file_name or "").lower() or True:
                    seen[f.file_id] = f
        except Exception:
            pass

    return list(seen.values())


# ─── Conversation entry: "🎭 Actors" button ───────────────────────────────────

@Client.on_callback_query(filters.regex(r"^actor_menu$"))
async def actor_menu(bot, query):
    """Entry point from start menu."""
    uid = query.from_user.id
    set_state(uid, "actor_search")
    await query.answer()

    text = (
        "🎭 **Actor / Director Search**\n\n"
        "Send the name of an actor or director.\n\n"
        "**Examples:**\n"
        "• Mohanlal\n"
        "• Mammootty\n"
        "• Tovino Thomas\n"
        "• Christopher Nolan\n"
        "• Lokesh Kanagaraj"
    )
    try:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅ Back", callback_data="back_start")
            ]]),
        )
    except MessageNotModified:
        pass


# ─── Message handler: intercept actor name input ──────────────────────────────

@Client.on_message(
    (filters.private | filters.group) & filters.text & filters.incoming,
    group=-5,    # higher priority than give_filter (group 0)
)
async def actor_name_handler(bot, message: Message):
    """Only fires when user is in actor_search state."""
    uid = message.from_user.id if message.from_user else 0
    if get_state(uid) != "actor_search":
        return

    name = (message.text or "").strip()
    if not name or name.startswith("/"):
        clear_state(uid)
        return

    # Stop this message from reaching auto_filter
    message.stop_propagation()
    clear_state(uid)

    slug = _slug(name)
    store_key = f"actor_{uid}_{slug}"

    # Show loading
    loading = await message.reply_text(f"🔍 Searching for **{name}**…")

    # Try to get a profile from IMDb (movie search as proxy)
    imdb_data = await get_poster(name)
    files     = await _fetch_actor_movies(name)

    if not files:
        await loading.edit_text(
            f"❌ No indexed movies found for **{name}**.\n\n"
            "Make sure the name is spelled correctly.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="actor_menu"),
                InlineKeyboardButton("⬅ Back",      callback_data="back_start"),
            ]]),
        )
        return

    ACTOR_RESULTS[store_key] = files
    total = len(files)

    # Build profile card
    text  = f"🎭 **{name}**\n\n"
    text += f"🎬 Found **{total}** indexed movies\n\n"

    if imdb_data:
        text += f"**Top Result:** {imdb_data.get('title', '')} ({imdb_data.get('year', '')})\n"
        langs = imdb_data.get('languages') or ""
        if langs and langs != "N/A":
            text += f"🌐 {langs}\n"

    text += "\nPress **🎬 View Movies** to browse with smart filters."

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 View Movies", callback_data=f"acvm_{uid}_{slug}")],
        [InlineKeyboardButton("🔄 New Search",  callback_data="actor_menu"),
         InlineKeyboardButton("⬅ Back",         callback_data="back_start")],
    ])
    await loading.edit_text(text, reply_markup=markup)


# ─── View Movies (with wizard) ────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^acvm_\d+_\w+$"))
async def actor_view_movies(bot, query):
    """Launch the dynamic filter wizard for actor results."""
    parts = query.data.split("_", 2)
    uid   = int(parts[1])
    slug  = parts[2]

    if query.from_user.id != uid:
        return await query.answer("Not your search 🔎", show_alert=True)

    store_key = f"actor_{uid}_{slug}"
    files     = ACTOR_RESULTS.get(store_key)

    if not files:
        return await query.answer("Session expired. Try again.", show_alert=True)

    await query.answer("Loading filters…")

    # ── Inject files into FILTER_STATE for the wizard ─────────────────────────
    from plugins.pm_filter import (
        FILTER_STATE, BUTTONS,
        _get_wizard_steps, _build_wizard_step, _show_wizard_results,
    )
    from plugins.pm_filter import STEP_ORDER

    key = f"actor_{uid}_{slug}"
    BUTTONS[key] = ""       # sentinel — files already in FILTER_STATE
    state = {
        "all_files":    files,
        "search":       slug.replace("_", " "),
        "lang": None, "year": None, "qual": None,
        "s": None,    "ep":   None,
    }

    wizard_steps = _get_wizard_steps(files)
    state["wizard_steps"] = wizard_steps
    state["wizard_step"]  = 0
    FILTER_STATE[key] = state

    result = _build_wizard_step(key, uid, state) if wizard_steps else None
    if result:
        wz_text, wz_markup = result
        try:
            await query.edit_message_text(wz_text, reply_markup=wz_markup)
        except MessageNotModified:
            pass
    else:
        await _show_wizard_results(query, key, uid)


# ─── Pagination ───────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^acnxt_\d+_\w+_\d+$"))
async def actor_next_page(bot, query):
    parts  = query.data.split("_", 3)
    uid    = int(parts[1])
    slug   = parts[2]
    offset = int(parts[3])

    if query.from_user.id != uid:
        return await query.answer("Not your search 🔎", show_alert=True)

    store_key = f"actor_{uid}_{slug}"
    files     = ACTOR_RESULTS.get(store_key)
    if not files:
        return await query.answer("Session expired.", show_alert=True)

    total      = len(files)
    page_files = files[offset: offset + FILES_PER_PAGE]
    settings   = await get_settings(query.message.chat.id)

    btn  = _build_file_buttons(page_files, settings)
    prow = _build_pagination(uid, slug, offset, total)
    if prow:
        btn.append(prow)
    btn.append([InlineKeyboardButton("⬅ Back", callback_data="back_start")])

    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass

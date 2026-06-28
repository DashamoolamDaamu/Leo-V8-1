# 🎬 Leo Advanced Filter Bot

A powerful, modern OTT-style Telegram Movie Auto Filter Bot built on top of the open-source **ShobanaFilterBot** by [mn-bots](https://github.com/mn-bots/ShobanaFilterBot).

---

## ✨ What's New in Leo Advanced Filter Bot

All new features added by **Shamil**, built on top of the original ShobanaFilterBot V8 architecture.

### 🎬 OTT-Style Start Menu
Modern home screen with quick access to all features — no extra plugin files, fully integrated into `commands.py` and `pm_filter.py`.

### 🔍 Smart Filter Wizard (Browse Mode Only)
Dynamic multi-level filter wizard that asks Language → Year → Quality → Season → Episode — but **only inside Browse Mode**. Normal Auto Filter works exactly like the original.

### 🎭 Actor / Director Search
- Search actors or directors by name
- Pulls filmography from IMDb
- Shows only movies available in MongoDB
- Never interferes with Auto Filter

### 🌐 Browse by Genre / Language / Year
- Genre browsing with IMDb metadata cache
- Language-based browsing
- Year-based browsing
- All results come from MongoDB only

### 🔥 Trending & ⭐ Top Rated
- Trending: based on search counts + view counts (database-driven)
- Top Rated: based on user movie ratings

### 🎯 Collections
Pre-built movie collections: Marvel, DC, Harry Potter, Mission Impossible, and more.

### 🆕 Latest Releases
Sorted by IMDb release year, only shows movies in the database.

### ⭐ Movie Rating System
After watching, users can rate movies: 👍 Good / 😐 Average / 👎 Bad

---

## 🏗 Architecture

All new features are integrated into the **existing ShobanaFilterBot V8 structure**:

| Feature | Where |
|---|---|
| Start Menu | `plugins/commands.py` + `plugins/pm_filter.py` |
| Normal Auto Filter | `plugins/pm_filter.py` (unchanged) |
| Browse Menu | `plugins/browse_menu.py` (new, independent) |
| Genre Browse | `plugins/genre_browse.py` (extended from v6) |
| Actor Search | `plugins/actor_search.py` (new, independent) |
| Smart Wizard | `plugins/pm_filter.py` (Browse/Actor modes only) |
| User States | `plugins/user_states.py` (tiny helper) |
| Ratings DB | `database/ratings_db.py` (new collection) |
| Actor Cache | `database/actor_cache_db.py` (new collection) |

---

## 📦 Original Credits

This project is based on the open-source **ShobanaFilterBot** by mn-bots.

- Original Repository: https://github.com/mn-bots/ShobanaFilterBot
- Original Developer: mn-bots

All original features, architecture, database layers, and callback systems are preserved intact.

New OTT features implemented by: **Shamil**

---

## ⚡ Key Rules

- ✅ Normal Auto Filter works exactly like original V8
- ✅ Smart Filter Wizard only runs in Browse Mode
- ✅ All movies come from MongoDB — never from IMDb directly  
- ✅ IMDb used only for metadata (poster, rating, cast, genres)
- ✅ No extra Start Menu plugin file
- ✅ No duplicate handlers or database methods
- ✅ All Back buttons work correctly

---

## 🚀 Deployment

Same as original ShobanaFilterBot — see original README for environment variables and setup.

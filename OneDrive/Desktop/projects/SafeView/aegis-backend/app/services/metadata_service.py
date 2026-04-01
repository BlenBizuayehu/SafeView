"""
Metadata service (FREQ-05) to query TMDb and decide ALLOW/BLOCK.
"""

from typing import Any
import os
import httpx

TMDB_API_BASE = "https://api.themoviedb.org/3"


async def analyze_metadata(title: str, blocked_themes: list[str]) -> dict[str, Any]:
    """
    Query TMDb search/multi and details (genres/keywords) and compare with blocked themes.

    Args:
        title: Title of the media to analyze.
        blocked_themes: List of blocked genres/keywords (case-insensitive).

    Returns:
        dict with keys:
            - status: "BLOCK" or "ALLOW"
            - reason: Explanation string
    """
    if not title:
        return {"status": "ALLOW", "reason": "No title provided"}

    api_key = os.getenv("TMDB_API_KEY", "")
    if not api_key:
        # In absence of API key, allow by default but note reason.
        return {"status": "ALLOW", "reason": "TMDb API key missing"}

    blocked = {t.strip().lower() for t in blocked_themes or [] if t and t.strip()}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1) Search across movies/TV
            search_resp = await client.get(
                f"{TMDB_API_BASE}/search/multi",
                params={"api_key": api_key, "query": title}
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()
            results = search_data.get("results") or []

            if not results:
                return {"status": "ALLOW", "reason": "No TMDb match found"}

            # Choose the top result
            top = results[0]
            media_type = top.get("media_type")
            tmdb_id = top.get("id")
            if not tmdb_id or media_type not in {"movie", "tv"}:
                return {"status": "ALLOW", "reason": "Unsupported media type or missing ID"}

            # 2) Fetch details (genres)
            details_resp = await client.get(
                f"{TMDB_API_BASE}/{media_type}/{tmdb_id}",
                params={"api_key": api_key}
            )
            details_resp.raise_for_status()
            details = details_resp.json()

            # 3) Fetch keywords
            if media_type == "movie":
                kw_endpoint = f"{TMDB_API_BASE}/movie/{tmdb_id}/keywords"
                kw_key = "keywords"
            else:
                kw_endpoint = f"{TMDB_API_BASE}/tv/{tmdb_id}/keywords"
                kw_key = "results"

            kw_resp = await client.get(kw_endpoint, params={"api_key": api_key})
            kw_resp.raise_for_status()
            kw_data = kw_resp.json()

            genres = [g.get("name", "") for g in (details.get("genres") or [])]
            keywords = [k.get("name", "") for k in (kw_data.get(kw_key) or [])]

            # Normalize and compare
            matched = []
            for g in genres:
                if g and g.strip().lower() in blocked:
                    matched.append(f"genre:{g}")
            for k in keywords:
                if k and k.strip().lower() in blocked:
                    matched.append(f"keyword:{k}")

            if matched:
                return {"status": "BLOCK", "reason": ", ".join(matched)}

            return {"status": "ALLOW", "reason": "No blocked themes matched"}

        except httpx.HTTPError as e:
            # On network/API errors, allow by default while noting reason.
            return {"status": "ALLOW", "reason": f"TMDb error: {str(e)}"}


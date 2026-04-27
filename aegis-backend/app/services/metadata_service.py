"""Metadata service to query TMDb and return moderation decisions."""

from __future__ import annotations

import os
from typing import Any

import httpx

TMDB_API_BASE = "https://api.themoviedb.org/3"


class MetadataService:
    """Service for TMDb metadata checks against restricted themes."""

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        self.api_key = api_key or os.getenv("TMDB_API_KEY", "")
        self.timeout = timeout
        self.restricted_tag_terms: set[str] = {
            "lgbt",
            "lgbtq",
            "lgbtq+",
            "gay",
            "lesbian",
            "bisexual",
            "transgender",
            "queer",
            "adult",
            "erotic",
            "erotica",
            "sex",
            "sexual content",
            "porn",
            "pornography",
            "nudity",
        }
        # Reserved for deployments that maintain a restricted TMDb genre-id allowlist.
        self.restricted_genre_ids: set[int] = set()

    def _match_restricted_tags(self, tags: list[str]) -> list[str]:
        matches: list[str] = []
        for raw_tag in tags:
            tag = (raw_tag or "").strip().lower()
            if not tag:
                continue
            if tag in self.restricted_tag_terms:
                matches.append(raw_tag)
                continue
            if any(term in tag for term in self.restricted_tag_terms):
                matches.append(raw_tag)
        return matches

    async def check_thematic_content(self, title: str) -> dict[str, Any]:
        """
        Search TMDb and evaluate metadata for restricted themes.

        Returns:
            dict with decision/status and matching context.
        """
        normalized_title = (title or "").strip()
        if not normalized_title:
            return {"status": "ALLOW", "decision": "ALLOW", "reason": "No title provided"}

        api_key = self.api_key or os.getenv("TMDB_API_KEY", "")
        if not api_key:
            return {
                "status": "ALLOW",
                "decision": "ALLOW",
                "reason": "TMDB_API_KEY is not configured",
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                search_resp = await client.get(
                    f"{TMDB_API_BASE}/search/multi",
                    params={"api_key": api_key, "query": normalized_title},
                )
                search_resp.raise_for_status()
                search_data = search_resp.json()
                results = search_data.get("results") or []

                first_match = next(
                    (
                        item
                        for item in results
                        if item.get("media_type") in {"movie", "tv"} and item.get("id")
                    ),
                    None,
                )
                if first_match is None:
                    return {
                        "status": "ALLOW",
                        "decision": "ALLOW",
                        "reason": "No TMDb movie/show match found",
                    }

                media_type = first_match["media_type"]
                tmdb_id = first_match["id"]

                details_resp = await client.get(
                    f"{TMDB_API_BASE}/{media_type}/{tmdb_id}",
                    params={"api_key": api_key},
                )
                details_resp.raise_for_status()
                details = details_resp.json()

                if media_type == "movie":
                    kw_endpoint = f"{TMDB_API_BASE}/movie/{tmdb_id}/keywords"
                    kw_key = "keywords"
                else:
                    kw_endpoint = f"{TMDB_API_BASE}/tv/{tmdb_id}/keywords"
                    kw_key = "results"

                kw_resp = await client.get(kw_endpoint, params={"api_key": api_key})
                kw_resp.raise_for_status()
                kw_data = kw_resp.json()

                genre_ids = [int(g.get("id")) for g in (details.get("genres") or []) if g.get("id") is not None]
                genre_names = [str(g.get("name", "")) for g in (details.get("genres") or [])]
                tags = [str(k.get("name", "")) for k in (kw_data.get(kw_key) or [])]

                matched_genre_ids = [gid for gid in genre_ids if gid in self.restricted_genre_ids]
                matched_tags = self._match_restricted_tags(tags + genre_names)
                adult_flag = bool(first_match.get("adult") or details.get("adult"))

                if matched_genre_ids or matched_tags or adult_flag:
                    return {
                        "status": "BLOCK",
                        "decision": "BLOCK",
                        "title": normalized_title,
                        "media_type": media_type,
                        "tmdb_id": tmdb_id,
                        "matches": {
                            "adult_flag": adult_flag,
                            "genre_ids": matched_genre_ids,
                            "tags": matched_tags,
                        },
                        "reason": "Restricted thematic metadata detected",
                    }

                return {
                    "status": "ALLOW",
                    "decision": "ALLOW",
                    "title": normalized_title,
                    "media_type": media_type,
                    "tmdb_id": tmdb_id,
                    "matches": {"adult_flag": False, "genre_ids": [], "tags": []},
                    "reason": "No restricted thematic metadata detected",
                }
            except httpx.HTTPError as exc:
                return {
                    "status": "ALLOW",
                    "decision": "ALLOW",
                    "reason": f"TMDb error: {str(exc)}",
                }


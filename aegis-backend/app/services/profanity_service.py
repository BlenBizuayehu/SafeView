"""
Profanity detection service (FREQ-04, BR-03, BR-05).
"""

from typing import Any
import re


# Simple blacklist; expand with real policy list in future phases.
BLACKLIST = [
    "damn",
    "hell",
    "shit",
    "fuck",
    "bitch",
]

# Precompile a regex with word boundaries, case-insensitive.
BLACKLIST_RE = re.compile(r"\\b(" + "|".join(map(re.escape, BLACKLIST)) + r")\\b", re.IGNORECASE)


def analyze_profanity(text: str) -> dict[str, Any]:
    """
    Scan input text for profanity using a word-boundary regex (BR-03).

    Enforces BR-05 by returning a standardized mute duration of 1.5 seconds
    when profanity is detected.

    Returns:
        - contains_profanity: bool
        - action: "MUTE" if profanity else "ALLOW"
        - duration: 1.5 (seconds) if profanity else 0.0
        - matched: list of profane words found
    """
    if not text:
        return {"contains_profanity": False, "action": "ALLOW", "duration": 0.0, "matched": []}

    matches = BLACKLIST_RE.findall(text or "")
    if matches:
        # Enforce BR-05: 1.5 seconds mute
        return {
            "contains_profanity": True,
            "action": "MUTE",
            "duration": 1.5,
            "matched": list({m.lower() for m in matches}),
        }

    return {"contains_profanity": False, "action": "ALLOW", "duration": 0.0, "matched": []}


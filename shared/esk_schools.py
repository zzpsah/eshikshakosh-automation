#!/usr/bin/env python3
"""e-ShikshaKosh school registry.

Maps a school to its Bitwarden credential keys and target UDISE. The teacher runner
reads this instead of hardcoding a school, so a new school is one line here (plus its
Bitwarden secrets) rather than a code change.
"""
from __future__ import annotations

# school_key -> {"udise": ..., "username_key": ..., "password_key": ..., "aliases": [...]}
SCHOOLS = {
    "UMV_SAHASPUR": {
        "udise": "10130106304",
        "username_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME",
        "password_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD",
        "aliases": ["sahaspur", "umv sahaspur", "uchcha madhyamik vidyalaya sahaspur"],
    },
    "UMV_TETAHALI": {
        "udise": "10160203806",
        "username_key": "ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME",
        "password_key": "ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD",
        "aliases": ["tetahali", "umv tetahali", "uchch madhyamik vidyalay tetahali"],
    },
}


def find(query: str):
    """Return the registry entry for a school name/alias/UDISE, or None."""
    q = (query or "").strip().lower()
    if not q:
        return None
    for entry in SCHOOLS.values():
        if q == entry["udise"]:
            return entry
    for key, entry in SCHOOLS.items():
        if q == key.lower():
            return entry
        if any(q == alias for alias in entry["aliases"]):
            return entry
    return None


def list_schools():
    return [
        {
            "key": key,
            "udise": entry["udise"],
            "aliases": entry["aliases"],
        }
        for key, entry in SCHOOLS.items()
    ]

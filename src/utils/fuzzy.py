"""Fuzzy ranking wrapper around rapidfuzz.

For places/items: feed all candidate (label, id) pairs and a query, get
back top matches by score, deduped by id keeping the highest-scoring label.
"""
from typing import Iterable

from rapidfuzz import fuzz, process


def rank(
    query: str,
    choices: Iterable[tuple[str, int]],
    limit: int = 8,
    cutoff: int = 60,
) -> list[tuple[str, int, float]]:
    """Rank `choices` against `query`.

    Returns up to `limit` (label, id, score) tuples sorted by score desc.
    `cutoff` filters out matches below that score (0-100).
    Deduped by id — when multiple labels point to the same id (e.g. an
    item's canonical name + aliases), keep only the best-scoring label.
    """
    q = (query or "").strip()
    if not q:
        return []

    pairs = list(choices)
    if not pairs:
        return []

    labels = [p[0] for p in pairs]
    matches = process.extract(
        q, labels, scorer=fuzz.WRatio,
        limit=len(labels),  # we'll dedupe and trim ourselves
        score_cutoff=cutoff,
    )

    seen: dict[int, tuple[str, float]] = {}
    for label, score, idx in matches:
        cid = pairs[idx][1]
        if cid not in seen or score > seen[cid][1]:
            seen[cid] = (label, score)

    out = sorted(
        ((lbl, cid, score) for cid, (lbl, score) in seen.items()),
        key=lambda x: -x[2],
    )
    return out[:limit]

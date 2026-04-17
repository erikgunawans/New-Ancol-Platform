"""Token-overlap ranking used by RKAB/RJPP matching (v1).

This is the v1 heuristic shared by:
  - services/api-gateway/routers/rkab.py `/match`
  - bjr/retroactive.py `_rank_rkab_candidates` and `_rank_rjpp_candidates`

v2 will replace this with Vertex embeddings + pgvector; keeping the contract
stable (name + confidence + rationale) makes the swap a one-file change.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class OverlapMatch:
    """A single ranked candidate: the source item + its score + rationale."""

    item: object  # the source row (RKABLineItem or RJPPTheme etc.)
    confidence: float  # normalized overlap [0.0, 1.0]
    overlap: int  # token intersection count
    denom: int  # query token count
    rationale: str


def rank_by_token_overlap[T](
    query: str,
    items: Sequence[T],
    haystack_of: Callable[[T], str],
    top_n: int = 3,
) -> list[OverlapMatch]:
    """Rank `items` by lowercased-token set overlap against `query`.

    Args:
        query: free-form search string (title + description combined).
        items: candidate rows to rank.
        haystack_of: function that extracts the searchable text from each row
            (e.g. `lambda r: f"{r.activity_name} {r.category} {r.description or ''}"`).
        top_n: max candidates to return. Pass 0 for unlimited.

    Returns candidates sorted by confidence descending, limited to `top_n`.
    Items with zero overlap are dropped.
    """
    query_tokens = set(query.lower().split())
    denom = max(len(query_tokens), 1)
    matches: list[OverlapMatch] = []
    for item in items:
        hay_tokens = set(haystack_of(item).lower().split())
        overlap = len(query_tokens & hay_tokens)
        if overlap == 0:
            continue
        confidence = min(overlap / denom, 1.0)
        matches.append(
            OverlapMatch(
                item=item,
                confidence=round(confidence, 2),
                overlap=overlap,
                denom=denom,
                rationale=f"Token overlap {overlap}/{denom}",
            )
        )
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches[:top_n] if top_n > 0 else matches

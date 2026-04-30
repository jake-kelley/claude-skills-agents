"""Reciprocal Rank Fusion for hybrid search result merging."""


def reciprocal_rank_fusion(ranked_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Fuse multiple ranked lists via RRF.

    Args:
        ranked_lists: List of ranked document ID lists (e.g., [fts_results, vec_results])
        k: RRF parameter (typically 60)

    Returns:
        List of (doc_id, rrf_score) sorted by score descending.
    """
    scores = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

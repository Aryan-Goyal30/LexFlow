"""Retrieval metrics for judgment search (Phase 4 evaluation).

Pure functions over ranked lists of judgment keys, so they are easy to test
and reuse. For a query with relevant set R and the top-k results T:

- Recall@k = |R ∩ T| / |R|
- Precision@k = |R ∩ T| / k (k fixed, as in the brief's precision@10; a
  query that returns fewer than k results is not rewarded for it)
- Reciprocal rank = 1 / rank of the first relevant result (0 if none in T)

Queries are handled explicitly, never silently:

- **no-answer** queries (empty R) are excluded from the averages above and
  reported separately: how many returned nothing at all in the top k;
- a relevant key that is **not in the corpus** is an error in the evaluation
  set: the query is excluded from every average and listed under ``errors``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueryResult:
    query_id: str
    kind: str
    relevant: frozenset[str]
    ranked: tuple[str, ...]  # judgment keys, best first


@dataclass(frozen=True)
class Scores:
    recall: float
    precision: float
    reciprocal_rank: float
    first_relevant_rank: int | None


@dataclass
class Summary:
    k: int
    queries: int  # scored (has relevant judgments, none missing)
    recall: float
    precision: float
    mrr: float
    no_answer_queries: int
    no_answer_empty: int  # no-answer queries that returned nothing in the top k
    errors: list[str] = field(default_factory=list)


def score(result: QueryResult, k: int) -> Scores:
    if k < 1:
        raise ValueError("k must be at least 1")
    if not result.relevant:
        raise ValueError(f"query {result.query_id} has no relevant judgments to score")
    top = result.ranked[:k]
    found = [i for i, key in enumerate(top, start=1) if key in result.relevant]
    hits = len(set(top) & result.relevant)
    return Scores(
        recall=hits / len(result.relevant),
        precision=hits / k,
        reciprocal_rank=1 / found[0] if found else 0.0,
        first_relevant_rank=found[0] if found else None,
    )


def summarise(results: Iterable[QueryResult], k: int, corpus_keys: set[str]) -> Summary:
    scored: list[Scores] = []
    errors: list[str] = []
    no_answer = no_answer_empty = 0
    for result in results:
        missing = sorted(result.relevant - corpus_keys)
        if missing:
            errors.append(f"{result.query_id}: not in the corpus: {', '.join(missing)}")
            continue
        if not result.relevant:
            no_answer += 1
            no_answer_empty += not result.ranked[:k]
            continue
        scored.append(score(result, k))
    n = len(scored)
    return Summary(
        k=k,
        queries=n,
        recall=round(sum(s.recall for s in scored) / n, 4) if n else 0.0,
        precision=round(sum(s.precision for s in scored) / n, 4) if n else 0.0,
        mrr=round(sum(s.reciprocal_rank for s in scored) / n, 4) if n else 0.0,
        no_answer_queries=no_answer,
        no_answer_empty=no_answer_empty,
        errors=errors,
    )


def by_kind(results: Sequence[QueryResult]) -> dict[str, list[QueryResult]]:
    groups: dict[str, list[QueryResult]] = {"all": list(results)}
    for result in results:
        groups.setdefault(result.kind, []).append(result)
    return groups


# --- graded relevance (Batch 2) -----------------------------------------------------------------
#
# nDCG@k over grades 0-3 (ANNOTATION_GUIDE.md section 4): gain 2^g - 1, discount
# log2(rank + 1), normalised by the ideal ordering of every graded judgment of
# the query (not only those retrieved). Judgments without a label count as
# grade 0; how many of the top k were unlabelled is reported beside the score,
# because pooled labels leave some results unjudged.


def ndcg(ranked: Sequence[str], grades: dict[str, int], k: int) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")
    if any(g < 0 or g > 3 for g in grades.values()):
        raise ValueError("grades run from 0 to 3")
    ideal = sorted(grades.values(), reverse=True)[:k]
    best = sum(((1 << g) - 1) / math.log2(rank + 1) for rank, g in enumerate(ideal, start=1))
    if best == 0:
        raise ValueError("no judgment has a grade above 0")
    seen: set[str] = set()
    gained = 0.0
    for rank, key in enumerate(ranked[:k], start=1):
        if key in seen:
            continue
        seen.add(key)
        gained += ((1 << grades.get(key, 0)) - 1) / math.log2(rank + 1)
    return gained / best


def unjudged(ranked: Sequence[str], grades: dict[str, int], k: int) -> int:
    """How many of the top k have no label at all (pool-based evaluation)."""
    return sum(1 for key in dict.fromkeys(ranked[:k]) if key not in grades)


def cohen_kappa(first: Sequence[bool], second: Sequence[bool]) -> float | None:
    """Agreement of two reviewers on relevant versus not relevant, beyond chance.

    None when it is undefined (no pairs, or both reviewers gave one answer only).
    """
    if len(first) != len(second):
        raise ValueError("the two reviewers must label the same pairs")
    n = len(first)
    if n == 0:
        return None
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / n
    p1, p2 = sum(first) / n, sum(second) / n
    chance = p1 * p2 + (1 - p1) * (1 - p2)
    if chance == 1:
        return None
    return (observed - chance) / (1 - chance)

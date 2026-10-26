"""Graded relevance sets for judgment search, and how they are scored (Batch 2).

A set is a folder, as in ``docs/phase7-prerequisites/ANNOTATION_GUIDE.md``
section 8, plus a ``set.json`` that says who wrote the labels:

* ``set.json``: ``name``, ``version``, ``label_origin``, ``guide_version``,
  ``reviewers`` (pseudonymous ids), optional ``corpus`` (``source_key``,
  ``manifest_sha256``) and ``notes``;
* ``queries.jsonl``: ``query_id``, ``area``, ``summary``, optional
  ``cutoff_date``, ``source_key``, ``cnr``, ``guide_version``;
* ``labels.jsonl``: ``query_id``, ``judgment`` (``source_key`` and ``id``
  or ``cnr``), ``grade`` (0-3), ``reason`` and ``passage`` (required for
  grades 2 and 3), ``reviewer``, ``labelled_on``, optional ``minutes_spent``.

``label_origin`` is one of:

* ``lawyer``: labelled by the named reviewers (their qualification is
  stated in the set's README, not verified by LexFlow);
* ``synthetic``: written by developers on invented judgments, to test the
  machinery only;
* ``citation-proxy``: derived from which judgments a query judgment cites.
  A citation is a signal, **not** a lawyer's relevance judgment, and results
  on such labels are always reported as a proxy;
* ``model-generated``: written by an AI assistant (named in ``reviewers``)
  on genuine judgments, each grade 2 or 3 tied to a passage of the
  judgment's own text. A technical check of the search machinery, **never**
  expert relevance, and always reported as model-generated.

Nothing here generates or guesses a label. Relevant means grade 2 or 3.
When several reviewers give the same pair different grades, scoring needs a
``resolved`` label for it (the guide's discussed resolution); until then the set is
refused for scoring, and ``agreement`` reports how far the reviewers agree.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lexflow import evaluation

LabelOrigin = Literal["lawyer", "synthetic", "citation-proxy", "model-generated"]
RELEVANT = 2
RESOLVED = "resolved"
PROXY_REVIEWER = "citation-proxy"
MAX_LINES = 50_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CorpusRef(_Strict):
    source_key: str = Field(min_length=1, max_length=63)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SetInfo(_Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    version: int = Field(ge=1)
    label_origin: LabelOrigin
    guide_version: str = Field(min_length=1, max_length=50)
    reviewers: list[str] = Field(default_factory=list, max_length=20)
    corpus: CorpusRef | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _reviewers(self) -> SetInfo:
        if self.label_origin in ("lawyer", "model-generated") and not self.reviewers:
            raise ValueError(
                f"a {self.label_origin} set must name who wrote its labels (reviewers)"
            )
        if RESOLVED in self.reviewers or PROXY_REVIEWER in self.reviewers:
            raise ValueError(f"{RESOLVED!r} and {PROXY_REVIEWER!r} are not reviewer ids")
        return self


class QueryCase(_Strict):
    query_id: str = Field(min_length=1, max_length=100)
    area: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=5000)
    cutoff_date: date | None = None
    source_key: str | None = Field(default=None, min_length=1, max_length=63)
    cnr: str | None = Field(default=None, min_length=1, max_length=100)
    guide_version: str | None = Field(default=None, min_length=1, max_length=50)


class JudgmentRef(_Strict):
    source_key: str = Field(min_length=1, max_length=63)
    id: str | None = Field(default=None, min_length=1, max_length=200)
    cnr: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _one(self) -> JudgmentRef:
        if (self.id is None) == (self.cnr is None):
            raise ValueError("a judgment is named by exactly one of id and cnr")
        return self

    @property
    def key(self) -> str:
        return judgment_key(self.source_key, id=self.id, cnr=self.cnr)


class Label(_Strict):
    query_id: str = Field(min_length=1, max_length=100)
    judgment: JudgmentRef
    grade: int = Field(ge=0, le=3)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    passage: str | None = Field(default=None, min_length=1, max_length=200)
    reviewer: str = Field(min_length=1, max_length=100)
    labelled_on: date
    minutes_spent: float | None = Field(default=None, ge=0, le=600)

    @model_validator(mode="after")
    def _why(self) -> Label:
        needs_why = self.grade >= RELEVANT and self.reviewer != PROXY_REVIEWER
        if needs_why and (self.reason is None or self.passage is None):
            raise ValueError("a grade 2 or 3 needs its one-line reason and the passage")
        return self


def judgment_key(source_key: str, *, id: str | None = None, cnr: str | None = None) -> str:
    """The key a set and a ranking share: ``source:id`` or ``source:cnr:CNR``."""
    if (id is None) == (cnr is None):
        raise ValueError("give exactly one of id and cnr")
    return f"{source_key}:{id}" if id is not None else f"{source_key}:cnr:{cnr}"


@dataclass(frozen=True)
class RelevanceSet:
    info: SetInfo
    queries: dict[str, QueryCase]
    labels: list[Label]

    def describe(self) -> str:
        """The wording every reported result must carry."""
        n = len(self.queries)
        if self.info.label_origin == "lawyer":
            names = ", ".join(self.info.reviewers)
            return f"lawyer-labelled ({n} query cases, reviewer(s) {names})"
        if self.info.label_origin == "synthetic":
            return f"SYNTHETIC labels ({n} queries): tests the machinery, not legal quality"
        if self.info.label_origin == "model-generated":
            names = ", ".join(self.info.reviewers)
            return (
                f"MODEL-GENERATED labels ({n} queries, by {names}): a technical check, "
                "not expert relevance"
            )
        return f"citation-derived proxy labels ({n} queries): NOT lawyer relevance"

    def grades(self) -> dict[str, dict[str, int]]:
        """query id -> judgment key -> the grade used for scoring."""
        by_pair: dict[tuple[str, str], list[Label]] = {}
        for label in self.labels:
            by_pair.setdefault((label.query_id, label.judgment.key), []).append(label)
        out: dict[str, dict[str, int]] = {q: {} for q in self.queries}
        unresolved: list[str] = []
        for (query, key), labels in sorted(by_pair.items()):
            resolved = [lab for lab in labels if lab.reviewer == RESOLVED]
            if resolved:
                out[query][key] = resolved[0].grade
            elif len({lab.grade for lab in labels}) == 1:
                out[query][key] = labels[0].grade  # one reviewer, or all agree
            else:
                unresolved.append(f"{query} / {key}")
        if unresolved:
            raise ValueError(
                "labels by several reviewers need a resolution: " + "; ".join(unresolved)
            )
        return out


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if number > MAX_LINES:
                raise ValueError(f"{path.name}: more than {MAX_LINES} lines")
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"{path.name} line {number}: not JSON ({error.msg})"
                    ) from error
    return rows


def load(folder: Path) -> RelevanceSet:
    """Read and check a set folder; every problem is reported, nothing is repaired."""
    info = SetInfo.model_validate_json((folder / "set.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    queries: dict[str, QueryCase] = {}
    for n, raw in enumerate(_jsonl(folder / "queries.jsonl"), start=1):
        try:
            query = QueryCase.model_validate(raw)
        except ValueError as error:
            problems.append(f"queries.jsonl line {n}: {error}")
            continue
        if query.query_id in queries:
            problems.append(f"queries.jsonl line {n}: {query.query_id} repeats")
        queries[query.query_id] = query
    labels: list[Label] = []
    seen: set[tuple[str, str, str]] = set()
    allowed = set(info.reviewers) | {RESOLVED}
    if info.label_origin == "citation-proxy":
        allowed = {PROXY_REVIEWER}
    for n, raw in enumerate(_jsonl(folder / "labels.jsonl"), start=1):
        try:
            label = Label.model_validate(raw)
        except ValueError as error:
            problems.append(f"labels.jsonl line {n}: {error}")
            continue
        where = f"labels.jsonl line {n}"
        if label.query_id not in queries:
            problems.append(f"{where}: unknown query {label.query_id}")
        if info.label_origin != "synthetic" and label.reviewer not in allowed:
            problems.append(f"{where}: reviewer {label.reviewer!r} is not listed in set.json")
        triple = (label.query_id, label.judgment.key, label.reviewer)
        if triple in seen:
            problems.append(f"{where}: {label.reviewer} labelled this pair twice")
        seen.add(triple)
        labels.append(label)
    if problems:
        raise ValueError("; ".join(problems))
    return RelevanceSet(info, queries, labels)


# --- scoring --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryScore:
    query_id: str
    recall: float
    precision: float
    reciprocal_rank: float
    ndcg: float
    unjudged: int


@dataclass(frozen=True)
class Report:
    label: str  # RelevanceSet.describe(): always shown with the numbers
    k: int
    queries: int
    recall: float
    precision: float
    mrr: float
    ndcg: float
    unjudged: int  # results in the top k that no one labelled (all queries)
    skipped: list[str]  # queries with no relevant judgment, or no ranking
    per_query: list[QueryScore]


def evaluate(relevance: RelevanceSet, rankings: Mapping[str, Sequence[str]], k: int) -> Report:
    """Recall@k, Precision@k, MRR and nDCG@k of ``rankings`` (query id -> keys, best first)."""
    grades = relevance.grades()
    scores: list[QueryScore] = []
    skipped: list[str] = []
    for query_id in sorted(relevance.queries):
        graded = grades[query_id]
        relevant = frozenset(key for key, g in graded.items() if g >= RELEVANT)
        if query_id not in rankings:
            skipped.append(f"{query_id}: no ranking was given")
            continue
        if not relevant:
            skipped.append(f"{query_id}: no judgment is graded 2 or 3")
            continue
        ranked = tuple(rankings[query_id])
        basic = evaluation.score(evaluation.QueryResult(query_id, "", relevant, ranked), k)
        scores.append(
            QueryScore(
                query_id,
                basic.recall,
                basic.precision,
                basic.reciprocal_rank,
                evaluation.ndcg(ranked, graded, k),
                evaluation.unjudged(ranked, graded, k),
            )
        )

    def mean(values: Iterable[float]) -> float:
        values = list(values)
        return round(sum(values) / len(values), 4) if values else 0.0

    return Report(
        label=relevance.describe(),
        k=k,
        queries=len(scores),
        recall=mean(s.recall for s in scores),
        precision=mean(s.precision for s in scores),
        mrr=mean(s.reciprocal_rank for s in scores),
        ndcg=mean(s.ndcg for s in scores),
        unjudged=sum(s.unjudged for s in scores),
        skipped=skipped,
        per_query=scores,
    )


@dataclass(frozen=True)
class Agreement:
    pairs: int
    kappa: float | None  # relevant (2-3) versus not (0-1), beyond chance
    exact: float | None  # share of pairs given the same grade


def agreement(relevance: RelevanceSet, first: str, second: str) -> Agreement:
    """How far two reviewers agree on the pairs both labelled (guide section 7)."""
    a = {
        (lab.query_id, lab.judgment.key): lab.grade
        for lab in relevance.labels
        if lab.reviewer == first
    }
    b = {
        (lab.query_id, lab.judgment.key): lab.grade
        for lab in relevance.labels
        if lab.reviewer == second
    }
    both = sorted(a.keys() & b.keys())
    if not both:
        return Agreement(0, None, None)
    kappa = evaluation.cohen_kappa(
        [a[p] >= RELEVANT for p in both], [b[p] >= RELEVANT for p in both]
    )
    exact = sum(a[p] == b[p] for p in both) / len(both)
    return Agreement(len(both), kappa, exact)


# --- annotation support ---------------------------------------------------------------------------


def candidate_pool(
    query_id: str,
    runs: Mapping[str, Sequence[str]],
    *,
    depth: int = 20,
    extra: Iterable[str] = (),
) -> list[str]:
    """The guide's pool: the union of each method's top ``depth`` plus extra keys.

    Shuffled by a hash of the query and key, so the order is the same on
    every run and says nothing about which method found a judgment.
    """
    keys = {key for ranked in runs.values() for key in ranked[:depth]} | set(extra)
    return sorted(keys, key=lambda key: hashlib.sha256(f"{query_id}|{key}".encode()).hexdigest())


def pool_rows(query_id: str, pool: Sequence[str]) -> list[dict[str, str]]:
    """Blank labelling rows for a reviewer: no grade, no method, no score."""
    return [
        {"query_id": query_id, "judgment": key, "grade": "", "reason": "", "passage": ""}
        for key in pool
    ]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def citation_proxy(
    query_id: str,
    query_key: str,
    query_text: str,
    citations: Mapping[str, Sequence[str]],
    *,
    labelled_on: date,
) -> list[dict[str, Any]]:
    """Proxy labels: collection judgments whose citation appears in the query text.

    ``citations`` maps a judgment key to the citation strings recorded for it
    (its citation and neutral citation, from the import; never guessed). A
    match is an exact, whitespace- and case-insensitive occurrence of at least
    6 characters. Each match becomes grade 2 by reviewer ``citation-proxy``;
    these are signals that a court relied on a judgment, not a lawyer's
    relevance judgment, and a set built from them has label_origin
    ``citation-proxy``.
    """
    text = _normalise(query_text)
    labels: list[dict[str, Any]] = []
    for key in sorted(citations):
        if key == query_key:
            continue
        found = [c for c in citations[key] if len(_normalise(c)) >= 6 and _normalise(c) in text]
        if found:
            source_key, _, ident = key.partition(":")
            ref: dict[str, str] = (
                {"source_key": source_key, "cnr": ident.removeprefix("cnr:")}
                if ident.startswith("cnr:")
                else {"source_key": source_key, "id": ident}
            )
            labels.append(
                {
                    "query_id": query_id,
                    "judgment": ref,
                    "grade": RELEVANT,
                    "reason": f"cited as {found[0]!r} (proxy, not a lawyer's judgment)",
                    "passage": None,
                    "reviewer": PROXY_REVIEWER,
                    "labelled_on": labelled_on.isoformat(),
                }
            )
    return labels

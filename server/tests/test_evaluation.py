"""Retrieval metrics: exact values, edge cases, and how bad data is reported."""

from __future__ import annotations

import pytest

from lexflow.evaluation import QueryResult, by_kind, score, summarise


def result(qid: str, relevant: set[str], ranked: list[str], kind: str = "lexical") -> QueryResult:
    return QueryResult(qid, kind, frozenset(relevant), tuple(ranked))


def test_recall_precision_and_reciprocal_rank() -> None:
    scores = score(result("q", {"a", "b"}, ["x", "a", "y", "b", "z"]), k=3)
    assert scores.recall == 0.5  # only a is in the top 3
    assert scores.precision == pytest.approx(1 / 3)
    assert scores.reciprocal_rank == 0.5 and scores.first_relevant_rank == 2


def test_precision_divides_by_k_even_when_fewer_results_come_back() -> None:
    scores = score(result("q", {"a"}, ["a"]), k=10)
    assert (scores.recall, scores.precision, scores.reciprocal_rank) == (1.0, 0.1, 1.0)


def test_a_miss_scores_zero() -> None:
    scores = score(result("q", {"a"}, ["x", "y"]), k=10)
    assert (scores.recall, scores.precision, scores.reciprocal_rank) == (0.0, 0.0, 0.0)
    assert scores.first_relevant_rank is None


def test_results_beyond_k_do_not_count() -> None:
    assert score(result("q", {"a"}, ["x", "y", "a"]), k=2).recall == 0.0


def test_duplicate_keys_in_a_ranking_count_once() -> None:
    assert score(result("q", {"a"}, ["a", "a"]), k=2).precision == 0.5


def test_invalid_scoring_is_refused() -> None:
    with pytest.raises(ValueError, match="k must be"):
        score(result("q", {"a"}, ["a"]), k=0)
    with pytest.raises(ValueError, match="no relevant"):
        score(result("q", set(), ["a"]), k=1)


def test_summary_averages_only_answerable_queries() -> None:
    results = [
        result("q1", {"a"}, ["a"]),
        result("q2", {"b"}, ["x", "b"]),
        result("q3", set(), [], kind="no-answer"),
        result("q4", set(), ["a"], kind="no-answer"),
    ]
    summary = summarise(results, k=10, corpus_keys={"a", "b", "x"})
    assert summary.queries == 2
    assert summary.recall == 1.0 and summary.mrr == 0.75 and summary.precision == 0.1
    assert (summary.no_answer_queries, summary.no_answer_empty) == (2, 1)
    assert summary.errors == []


def test_relevant_judgments_missing_from_the_corpus_are_errors_not_misses() -> None:
    results = [result("q1", {"a", "gone"}, ["a"]), result("q2", {"a"}, ["a"])]
    summary = summarise(results, k=10, corpus_keys={"a"})
    assert summary.queries == 1 and summary.recall == 1.0
    assert summary.errors == ["q1: not in the corpus: gone"]


def test_an_empty_evaluation_reports_zero_queries() -> None:
    summary = summarise([], k=10, corpus_keys=set())
    assert (summary.queries, summary.recall, summary.mrr) == (0, 0.0, 0.0)


def test_grouping_by_kind_keeps_everything_under_all() -> None:
    results = [result("q1", {"a"}, [], "lexical"), result("q2", {"a"}, [], "paraphrase")]
    groups = by_kind(results)
    assert [r.query_id for r in groups["all"]] == ["q1", "q2"]
    assert [r.query_id for r in groups["paraphrase"]] == ["q2"]

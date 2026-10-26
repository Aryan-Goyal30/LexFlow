"""Graded relevance sets and their metrics (Batch 2).

Every set, query, judgment key and label here is INVENTED for the test; the
expected numbers are worked out by hand in the comments. No label is a
lawyer's, and nothing here measures legal quality.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from lexflow import evaluation
from lexflow import relevance_sets as sets

DAY = "2026-10-25"


def label(query: str, ident: str, grade: int, reviewer: str = "r1", **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "query_id": query,
        "judgment": {"source_key": "syn", "id": ident},
        "grade": grade,
        "reviewer": reviewer,
        "labelled_on": DAY,
    }
    if grade >= 2:
        row |= {"reason": "invented reason", "passage": "p. 1"}
    return row | extra


def write_set(tmp_path: Path, labels: list[dict[str, Any]], **info: Any) -> Path:
    folder = tmp_path / "set"
    folder.mkdir(exist_ok=True)
    meta = {
        "name": "syn-graded",
        "version": 1,
        "label_origin": "synthetic",
        "guide_version": "draft-1",
        "reviewers": ["r1", "r2"],
    } | info
    (folder / "set.json").write_text(json.dumps(meta), encoding="utf-8")
    queries = [
        {"query_id": q, "area": "Trade marks", "summary": f"Invented query {q} (SYNTHETIC)."}
        for q in ("q1", "q2", "q3")
    ]
    (folder / "queries.jsonl").write_text(
        "\n".join(json.dumps(q) for q in queries), encoding="utf-8"
    )
    (folder / "labels.jsonl").write_text(
        "\n".join(json.dumps(lab) for lab in labels), encoding="utf-8"
    )
    return folder


# --- metrics -------------------------------------------------------------------------------------


def test_ndcg_matches_a_hand_computation() -> None:
    grades = {"a": 3, "b": 2, "c": 0}
    # DCG@3 of [c, a, x]: 0 + 7/log2(3) + 0; ideal [3, 2, 0]: 7/1 + 3/log2(3) + 0.
    expected = (7 / math.log2(3)) / (7 + 3 / math.log2(3))
    assert evaluation.ndcg(["c", "a", "x", "b"], grades, 3) == pytest.approx(expected)
    assert evaluation.ndcg(["a", "b", "c"], grades, 3) == pytest.approx(1.0)
    assert evaluation.ndcg(["x", "y"], grades, 3) == 0.0
    # A repeated key earns nothing the second time.
    assert evaluation.ndcg(["a", "a"], {"a": 3, "b": 3}, 2) < 1.0
    assert evaluation.unjudged(["c", "a", "x", "x", "y"], grades, 5) == 2


@pytest.mark.parametrize(("grades", "k"), [({"a": 0}, 3), ({"a": 4}, 3), ({"a": 2}, 0)])
def test_ndcg_refuses_what_it_cannot_score(grades: dict[str, int], k: int) -> None:
    with pytest.raises(ValueError):
        evaluation.ndcg(["a"], grades, k)


def test_cohen_kappa_matches_a_hand_computation() -> None:
    # Observed 3/4; chance 0.5*0.25 + 0.5*0.75 = 0.5; kappa (0.75 - 0.5) / 0.5.
    first, second = [True, True, False, False], [True, False, False, False]
    assert evaluation.cohen_kappa(first, second) == pytest.approx(0.5)
    assert evaluation.cohen_kappa([True, True], [True, True]) is None
    assert evaluation.cohen_kappa([], []) is None


# --- sets ----------------------------------------------------------------------------------------


def test_a_set_is_scored_with_every_metric_and_its_label(tmp_path: Path) -> None:
    folder = write_set(
        tmp_path,
        [
            label("q1", "a", 3),
            label("q1", "b", 2),
            label("q1", "c", 1),
            label("q2", "d", 3),
            label("q3", "e", 1),  # no relevant judgment: skipped, and said so
        ],
    )
    relevance = sets.load(folder)
    report = sets.evaluate(
        relevance, {"q1": ["syn:c", "syn:a", "syn:z"], "q2": ["syn:d"], "q3": ["syn:e"]}, k=3
    )
    assert report.label.startswith("SYNTHETIC labels (3 queries)")
    assert report.queries == 2
    # q1: recall 1/2, precision 1/3, RR 1/2; q2: 1, 1/3, 1.
    assert report.recall == pytest.approx(0.75)
    assert report.precision == pytest.approx(round(1 / 3, 4))
    assert report.mrr == pytest.approx(0.75)
    q1 = report.per_query[0]
    assert q1.ndcg == pytest.approx(
        (1 / 1 + 7 / math.log2(3)) / (7 + 3 / math.log2(3) + 1 / 2), abs=1e-9
    )
    assert report.unjudged == 1  # "syn:z" in q1
    assert report.skipped == ["q3: no judgment is graded 2 or 3"]


def test_lawyer_sets_name_their_reviewers_and_keep_to_them(tmp_path: Path) -> None:
    folder = write_set(tmp_path, [label("q1", "a", 3)], label_origin="lawyer", reviewers=[])
    with pytest.raises(ValueError, match="must name who wrote"):
        sets.load(folder)
    folder = write_set(tmp_path, [label("q1", "a", 3, reviewer="r9")], label_origin="lawyer")
    with pytest.raises(ValueError, match="'r9' is not listed"):
        sets.load(folder)
    folder = write_set(tmp_path, [label("q1", "a", 3)], label_origin="lawyer")
    assert sets.load(folder).describe() == "lawyer-labelled (3 query cases, reviewer(s) r1, r2)"


@pytest.mark.parametrize(
    ("row", "problem"),
    [
        (label("q1", "a", 2) | {"reason": None}, "one-line reason"),
        (label("q9", "a", 1), "unknown query q9"),
        (label("q1", "a", 5), "less than or equal to 3"),
        (label("q1", "a", 1) | {"judgment": {"source_key": "syn"}}, "exactly one of id and cnr"),
    ],
)
def test_bad_labels_are_refused(tmp_path: Path, row: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        sets.load(write_set(tmp_path, [row]))


def test_several_reviewers_need_a_resolution_and_their_agreement_is_reported(
    tmp_path: Path,
) -> None:
    rows = [
        label("q1", "a", 3, "r1"),
        label("q1", "a", 1, "r2"),
        label("q1", "b", 2, "r1"),
        label("q1", "b", 2, "r2"),
    ]
    relevance = sets.load(write_set(tmp_path, rows, label_origin="lawyer"))
    with pytest.raises(ValueError, match="need a resolution: q1 / syn:a"):
        relevance.grades()
    agreed = sets.agreement(relevance, "r1", "r2")
    assert (agreed.pairs, agreed.exact) == (2, 0.5)
    # Observed 1/2; chance 1 * 1/2 + 0 * 1/2 = 1/2: no better than chance.
    assert agreed.kappa == pytest.approx(0.0)
    rows.append(label("q1", "a", 2, "resolved"))
    resolved = sets.load(write_set(tmp_path, rows, label_origin="lawyer"))
    assert resolved.grades()["q1"] == {"syn:a": 2, "syn:b": 2}


# --- annotation support --------------------------------------------------------------------------


def test_the_pool_is_the_union_of_runs_in_an_order_that_hides_the_method() -> None:
    runs = {"keyword": ["a", "b", "c"], "semantic": ["c", "d"], "hybrid": ["a", "e"]}
    pool = sets.candidate_pool("q1", runs, depth=2, extra=["f"])
    assert sorted(pool) == ["a", "b", "c", "d", "e", "f"]
    assert pool == sets.candidate_pool(
        "q1", dict(reversed(list(runs.items()))), depth=2, extra=["f"]
    )
    rows = sets.pool_rows("q1", pool)
    assert {tuple(r) for r in rows} == {("query_id", "judgment", "grade", "reason", "passage")}
    assert all(r["grade"] == "" for r in rows)


def test_citation_proxy_labels_are_marked_as_a_proxy(tmp_path: Path) -> None:
    text = "INVENTED. As held in  (SYN) 2099   TEST 7, and in sha-free 2099 SYN 9."
    citations = {
        "syn:a": ["(SYN) 2099 TEST 7"],
        "syn:b": ["2099 SYN 9", "short"],
        "syn:c": ["(SYN) 2099 TEST 8"],
        "syn:q": ["2099 SYN 9"],  # the query judgment itself is never its own label
    }
    rows = sets.citation_proxy("q1", "syn:q", text, citations, labelled_on=date(2026, 10, 25))
    assert [r["judgment"]["id"] for r in rows] == ["a", "b"]
    assert all(r["reviewer"] == "citation-proxy" and r["grade"] == 2 for r in rows)
    assert "proxy, not a lawyer's judgment" in rows[0]["reason"]
    folder = write_set(tmp_path, rows, label_origin="citation-proxy", reviewers=[])
    relevance = sets.load(folder)
    assert relevance.describe().endswith("NOT lawyer relevance")
    lawyer_style = write_set(tmp_path, [label("q1", "a", 3, "r1")], label_origin="citation-proxy")
    with pytest.raises(ValueError, match="not listed"):
        sets.load(lawyer_style)


def test_model_generated_labels_are_named_as_such_and_need_their_author(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must name who wrote"):
        sets.load(write_set(tmp_path, [label("q1", "a", 3)], label_origin="model-generated",
                            reviewers=[]))  # fmt: skip
    folder = write_set(
        tmp_path, [label("q1", "a", 3, "claude-code")],
        label_origin="model-generated", reviewers=["claude-code"],
    )  # fmt: skip
    described = sets.load(folder).describe()
    assert described.startswith("MODEL-GENERATED labels (3 queries, by claude-code)")
    assert described.endswith("not expert relevance")

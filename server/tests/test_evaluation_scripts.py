"""The throwaway-database guard of the retrieval and judgment-search evaluation
scripts (Phase 5 M9 review, finding M1). Nothing here connects to a database:
the URL is checked offline, and ``main`` is shown to refuse before it loads a
model, reads a file or touches a server."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
NAMES = ("evaluate_judgment_search", "evaluate_retrieval")


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"lexflow_eval_{name}", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=NAMES)
def script(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = load(request.param)

    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the guard must refuse before anything is connected or loaded")

    for name in ("create_engine", "recreate", "migrate", "LocalBgeProvider", "load_set"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, never)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test?dbname=lexflow",
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test?service=live",
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test?sslmode=disable&dbname=lexflow",
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_eval_test?dbname=lexflow_eval_test",
    ],
)
def test_a_url_that_could_connect_elsewhere_is_refused(
    script: ModuleType, url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(SystemExit, match="dbname or service"):
        script.eval_url()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test",
        "postgresql+psycopg://u@localhost/lexflow_test",
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test?sslmode=disable",
        "postgresql+psycopg://u:p@127.0.0.1:5432/lexflow_test?connect_timeout=5",
    ],
)
def test_a_supported_url_names_only_the_throwaway_database(
    script: ModuleType, url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    chosen = script.eval_url()
    assert chosen.database == "lexflow_eval_test" == script.DATABASE
    assert not {"dbname", "service"} & set(chosen.query)


def test_main_refuses_before_any_side_effect(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1/lexflow_test?dbname=lexflow"
    )
    monkeypatch.setattr(sys, "argv", [script.__name__])
    with pytest.raises(SystemExit, match="dbname or service"):
        script.main()

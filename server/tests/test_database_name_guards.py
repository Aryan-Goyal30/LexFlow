"""The database-name guards of the test setup and the e2e harness (Phase 5 M10,
finding L2): a name qualifies only when "test" (or "e2e") is a whole part of
it, and a URL that could connect to another database is refused. Nothing here
connects to a database."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import make_url

from tests.conftest import _guard, is_test_name

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.parametrize(
    ("name", "allowed"),
    [
        ("lexflow_test", True),
        ("lexflow_migration_test", True),
        ("lexflow_seed_test", True),
        ("lexflow_eval_test", True),
        ("test", True),
        ("lexflow", False),
        ("lexflow_latest", False),
        ("contest", False),
        ("lexflowtest", False),
        ("lexflow_e2e", False),  # the test suite never drops the e2e database
        ("", False),
    ],
)
def test_the_test_setup_modifies_only_databases_named_for_tests(name: str, allowed: bool) -> None:
    assert is_test_name(name) is allowed
    url = make_url(f"postgresql+psycopg://u:p@127.0.0.1/{name}")
    if allowed:
        assert _guard(url) == name
    else:
        with pytest.raises(ValueError, match="refusing to modify"):
            _guard(url)


@pytest.mark.parametrize("query", ["?dbname=lexflow", "?service=live"])
def test_the_test_setup_refuses_a_url_that_connects_elsewhere(query: str) -> None:
    with pytest.raises(ValueError, match="refusing to modify"):
        _guard(make_url(f"postgresql+psycopg://u:p@127.0.0.1/lexflow_test{query}"))


def e2e_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_e2e_script", SCRIPTS / "e2e.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "allowed"),
    [
        ("lexflow_e2e", True),
        ("e2e", True),
        ("lexflow-e2e-2", True),
        ("lexflow", False),
        ("note2e", False),
        ("lexflowe2e", False),
        ("lexflow_test", False),
    ],
)
def test_the_e2e_harness_drops_only_a_database_named_for_e2e(
    name: str, allowed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = e2e_script()
    monkeypatch.setenv("LEXFLOW_E2E_DATABASE", name)
    if allowed:
        assert script.e2e_database_url().database == name
    else:
        with pytest.raises(SystemExit, match="'e2e' must be a part of its name"):
            script.e2e_database_url()

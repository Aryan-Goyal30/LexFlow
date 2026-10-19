"""Six people in different relationships to the sample Sattvik case (case-1005).

- admin: an Administrator (every case);
- lead: Aryan Goyal, its lead advocate;
- associate: an Advocate on its team;
- paralegal: a Paralegal assigned to it;
- other_advocate: Rajat Deshpande, who leads a different case;
- other_paralegal: a Paralegal assigned to nothing.

``as_("lead")`` gives an HTTP client signed in as that person. Registered for
all tests through ``pytest_plugins`` in ``tests/conftest.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from lexflow.auth.passwords import hash_password
from lexflow.clock import get_today
from lexflow.models import CaseMember, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from tests.conftest import TEST_PASSWORD, http_client, make_user, sign_in
from tests.test_cases import TODAY  # the fixed date the case tests run on

SATTVIK = sample_uuid("case", "case-1005")


@pytest.fixture
def people(db: Session, app: FastAPI, storage_root: Any) -> dict[str, User]:
    load_sample_data(db)
    db.commit()
    app.dependency_overrides[get_today] = lambda: TODAY

    def can_sign_in(user_id: uuid.UUID) -> User:
        user = db.get(User, user_id)
        assert user is not None
        user.password_hash = hash_password(TEST_PASSWORD, "test-fast")
        return user

    lead = can_sign_in(sample_uuid("advocate", "Aryan Goyal"))
    other_advocate = can_sign_in(sample_uuid("advocate", "Rajat Deshpande"))
    db.commit()
    team = {
        "admin": make_user(db, role="Administrator"),
        "lead": lead,
        "associate": make_user(db, role="Advocate", name="Associate Advocate"),
        "paralegal": make_user(db, role="Paralegal", name="Assigned Paralegal"),
        "other_advocate": other_advocate,
        "other_paralegal": make_user(db, role="Paralegal", name="Unassigned Paralegal"),
    }
    db.add_all(
        [
            CaseMember(case_id=SATTVIK, user_id=team["associate"].id, member_role="associate"),
            CaseMember(case_id=SATTVIK, user_id=team["paralegal"].id, member_role="paralegal"),
        ]
    )
    db.commit()
    return team


@pytest.fixture
def storage_root(tmp_path: Any, app: FastAPI) -> Any:
    from lexflow.storage import LocalDiskStorage, get_storage

    root = tmp_path / "uploads"
    app.dependency_overrides[get_storage] = lambda: LocalDiskStorage(root)
    return root


@pytest.fixture
def as_(app: FastAPI, people: dict[str, User]) -> Iterator[Callable[[str], TestClient]]:
    """``as_("lead")``: a client signed in as that person."""
    with ExitStack() as stack:
        signed_in: dict[str, TestClient] = {}

        def get(role: str) -> TestClient:
            if role not in signed_in:
                http = stack.enter_context(http_client(app, raise_server_exceptions=False))
                sign_in(http, people[role])
                signed_in[role] = http
            return signed_in[role]

        yield get

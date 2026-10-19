"""Signing in and out, the current user, and changing one's own password.

The session token travels only in an HttpOnly, SameSite=Strict cookie (Secure
when ``LEXFLOW_COOKIE_SECURE`` is on; required in production). It is never in a
response body, a URL or a log. The cookie has no Max-Age: it ends with the
browser session, and the server enforces the idle and absolute limits.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth import service
from lexflow.auth.deps import Principal, require_session, session_token
from lexflow.clock import get_now
from lexflow.config import Settings, get_settings
from lexflow.db import IndependentSessions, get_independent_sessions, get_session
from lexflow.errors import problem_responses
from lexflow.models import User
from lexflow.schemas import MeOut, PasswordChangeIn, SignInIn

router = APIRouter(prefix="/auth", tags=["authentication"])


def me_out(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]  # the database constrains the value
        client_id=user.client_id,
        must_change_password=user.must_change_password,
    )


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/login", response_model=MeOut, responses=problem_responses(401, 422))
def login(
    data: SignInIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    independent: IndependentSessions = Depends(get_independent_sessions),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> MeOut:
    """Sign in with e-mail and password. Sets the session cookie.

    Every refusal is the same 401 ``invalid-credentials``, whatever the reason.
    """
    signed_in = service.sign_in(
        session,
        independent,
        audit,
        email=data.email,
        password=data.password,
        now=now,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
        previous_token=session_token(request, settings),
    )
    set_session_cookie(response, signed_in.token, settings)
    response.headers["Cache-Control"] = "no-store"
    return me_out(signed_in.user)


@router.post("/logout", status_code=204, response_class=Response)
def logout(
    request: Request,
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> Response:
    """End the current session (if any) and clear the cookie. Always 204."""
    service.sign_out(
        session, audit, token=session_token(request, settings), now=now, settings=settings
    )
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=MeOut, responses=problem_responses(401))
def me(principal: Principal = Depends(require_session)) -> MeOut:
    """Who is signed in. 401 ``not-authenticated`` without a live session."""
    return me_out(principal.user)


@router.post("/password", response_model=MeOut, responses=problem_responses(401, 422))
def change_password(
    data: PasswordChangeIn,
    request: Request,
    response: Response,
    principal: Principal = Depends(require_session),
    session: Session = Depends(get_session),
    independent: IndependentSessions = Depends(get_independent_sessions),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> MeOut:
    """Replace your own password (also a temporary one). Ends your other sessions."""
    token = service.change_own_password(
        session,
        independent,
        audit,
        user=principal.user,
        live=principal.session,
        current_password=data.current_password,
        new_password=data.new_password,
        now=now,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, token, settings)
    response.headers["Cache-Control"] = "no-store"
    return me_out(principal.user)

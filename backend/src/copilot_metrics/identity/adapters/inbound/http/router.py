"""Inbound HTTP routes of identity: GitHub sign-in, sign-out and the session endpoint."""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse, Response

from copilot_metrics.identity.adapters.inbound.http.dependencies import Guards
from copilot_metrics.identity.domain import Access, SessionUser, SignInFailed
from copilot_metrics.identity.service import SignInService
from copilot_metrics.shared.adapters.inbound.http.middleware import USER_KEY
from copilot_metrics.shared.kernel import Frozen, Role

log = logging.getLogger(__name__)

_STATE_KEY = "oauth_state"


class SessionView(Frozen):
    login: str
    user_id: int
    name: str | None
    avatar_url: str | None
    role: Role
    has_seat: bool
    access: Access


def build_auth_router(*, service: SignInService, guards: Guards, public_url: str) -> APIRouter:
    router = APIRouter()
    redirect_uri = f"{public_url.rstrip('/')}/auth/github/callback"

    @router.get("/auth/github", include_in_schema=False)
    def sign_in(request: Request) -> RedirectResponse:
        state = secrets.token_urlsafe(32)
        request.session.clear()
        request.session[_STATE_KEY] = state
        return RedirectResponse(service.start(state=state, redirect_uri=redirect_uri))

    @router.get("/auth/github/callback", include_in_schema=False)
    async def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
        expected = request.session.pop(_STATE_KEY, None)
        if not code or not expected or not secrets.compare_digest(state, expected):
            return RedirectResponse("/?signin_error=state")
        try:
            user = await service.complete(code=code, redirect_uri=redirect_uri)
        except SignInFailed as exc:
            log.warning("GitHub refused sign-in: %s", exc.message)
            return RedirectResponse("/?signin_error=github")
        except Exception:  # a browser redirect: never show a JSON error page mid-OAuth
            log.exception("GitHub sign-in failed")
            return RedirectResponse("/?signin_error=github")
        request.session.clear()
        request.session[USER_KEY] = user.model_dump(mode="json")
        return RedirectResponse("/")

    @router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def sign_out(request: Request) -> Response:
        request.session.clear()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/api/session")
    async def session(user: Annotated[SessionUser, Depends(guards.current_user)]) -> SessionView:
        has_seat = await guards.has_seat(user.viewer())
        return SessionView(
            login=user.login,
            user_id=user.user_id,
            name=user.name,
            avatar_url=user.avatar_url,
            role=user.role,
            has_seat=has_seat,
            access=Access.of(user.role, has_seat),
        )

    return router

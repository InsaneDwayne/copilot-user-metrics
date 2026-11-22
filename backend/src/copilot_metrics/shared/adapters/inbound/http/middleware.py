"""HTTP middleware of the API."""

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from copilot_metrics.settings import SessionSettings

USER_KEY = "user"  # the session entry holding the signed-in user (identity's ``SessionUser``)


def install_session_middleware(app: FastAPI, settings: SessionSettings, *, https: bool) -> None:
    """Signed session cookie. It holds only who you are - never a GitHub token.

    The cookie's ``max_age`` matches the absolute session lifetime, which the
    identity guards also enforce server-side via ``signed_in_at``. ``https`` (the public
    URL's scheme) sets its Secure flag.
    """
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret.get_secret_value(),
        session_cookie=settings.cookie_name,
        max_age=int(settings.max_age.total_seconds()),
        same_site="lax",
        https_only=https,
    )

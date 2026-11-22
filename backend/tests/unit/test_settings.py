import httpx
import pytest
from fastapi import FastAPI, Request
from pydantic import ValidationError

from copilot_metrics.settings import ApiSettings, ConfigurationError, GitHubSettings, SessionSettings, Settings
from copilot_metrics.shared.adapters.inbound.http.middleware import install_session_middleware

SECRET = "s" * 32
DB = "postgresql://api:api@db/metrics"


def _settings(public_url: str, *, allow_http: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        github=GitHubSettings(org="acme-labs", app_client_id="id", app_client_secret="secret"),
        api=ApiSettings.model_validate({"database_url": DB, "public_url": public_url, "allow_http": allow_http}),
        session=SessionSettings(secret=SECRET),
    )


@pytest.mark.parametrize("secret", ["", "changeme", "s" * 31])
def test_a_short_session_secret_is_refused(secret: str) -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        SessionSettings(secret=secret)


def test_a_32_character_session_secret_is_accepted() -> None:
    assert SessionSettings(secret=SECRET).secret.get_secret_value() == SECRET


@pytest.mark.parametrize(
    ("public_url", "https"),
    [
        ("https://copilot.acme.internal", True),
        ("https://copilot.acme.internal:8443/", True),
        ("http://localhost:5173", False),
        ("http://127.0.0.1:8000", False),
        ("http://[::1]:8000", False),
    ],
)
def test_https_and_loopback_urls_start(public_url: str, https: bool) -> None:
    api, _ = _settings(public_url).require_api()
    assert api.https is https  # the session cookie's Secure flag


@pytest.mark.parametrize("public_url", ["http://copilot.acme.internal", "http://10.0.0.5:8000"])
def test_plain_http_on_the_network_is_refused(public_url: str) -> None:
    with pytest.raises(ConfigurationError, match="API_ALLOW_HTTP"):
        _settings(public_url).require_api()


def test_plain_http_mode_allows_http_on_the_network() -> None:
    api, _ = _settings("http://test-box:8000", allow_http=True).require_api()
    assert api.https is False


@pytest.mark.parametrize("public_url", ["copilot.acme.internal", "ftp://copilot.acme.internal", "https://"])
def test_a_public_url_that_is_not_http_is_refused(public_url: str) -> None:
    with pytest.raises(ConfigurationError, match="must be an http"):
        _settings(public_url, allow_http=True).require_api()


@pytest.mark.parametrize("https", [True, False])
async def test_the_session_cookie_is_secure_over_https(https: bool) -> None:
    app = FastAPI()
    install_session_middleware(app, SessionSettings(secret=SECRET), https=https)

    @app.get("/")
    def sign_in(request: Request) -> None:
        request.session["user"] = "mona"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        cookie = (await client.get("/")).headers["set-cookie"].lower()
    assert ("; secure" in cookie) is https

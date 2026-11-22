"""mount_spa serves files inside the static root only; anything else falls back to index.html."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from starlette.types import Message

from copilot_metrics.shared.adapters.inbound.http.error_handlers import install_error_handlers
from copilot_metrics.shared.adapters.inbound.http.spa import mount_spa

INDEX = "<!doctype html><title>dashboard</title>"
SECRET = "outside the static root"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """<tmp>/secret.txt next to <tmp>/static, the root, which links out of itself."""
    (tmp_path / "secret.txt").write_text(SECRET)
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "key.pem").write_text(SECRET)
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(INDEX)
    (static / "favicon.svg").write_text("<svg/>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (static / "theme").mkdir()
    (static / "theme" / "theme.json").write_text("{}")
    (static / "leak.txt").symlink_to(tmp_path / "secret.txt")
    (static / "private").symlink_to(tmp_path / "private", target_is_directory=True)
    return static


@pytest.fixture
async def http(root: Path) -> AsyncGenerator[httpx.AsyncClient]:
    app = FastAPI()
    install_error_handlers(app)
    mount_spa(app, root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        yield client


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/", INDEX),
        ("/favicon.svg", "<svg/>"),
        ("/theme/theme.json", "{}"),
        ("/assets/app.js", "console.log(1)"),
        ("/admin/members", INDEX),  # client-side route
    ],
)
async def test_files_inside_the_root_are_served(http: httpx.AsyncClient, path: str, body: str) -> None:
    response = await http.get(path)
    assert response.status_code == 200
    assert response.text == body


@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/secret.txt",
        "/%2E%2E/secret.txt",
        "/theme/%2e%2e/%2e%2e/secret.txt",
        "/..%2fsecret.txt",
        "/%2e%2e%2fsecret.txt",
        "/theme/..%2f..%2fsecret.txt",
        "/leak.txt",  # symlink to a file outside the root
        "/private/key.pem",  # through a symlinked directory
        "/%2Fetc%2Fpasswd",  # an absolute path would replace the root in root / path
    ],
)
async def test_paths_leaving_the_root_get_index_html(http: httpx.AsyncClient, path: str) -> None:
    response = await http.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert SECRET not in response.text


@pytest.mark.parametrize("path", ["/../secret.txt", "/theme/../../secret.txt", "/assets/../../secret.txt"])
async def test_raw_dot_dot_segments_get_index_html(root: Path, path: str) -> None:
    """Sent as raw ASGI, so no client normalises the path before the app sees it."""
    app = FastAPI()
    mount_spa(app, root)
    requested = False
    body: list[bytes] = []

    async def receive() -> Message:
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()  # the client never disconnects
        raise AssertionError("unreachable")

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body":
            body.append(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "server": ("test", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    text = b"".join(body).decode()
    assert SECRET not in text
    assert text == INDEX or "not found" in text.lower()


@pytest.mark.parametrize("path", ["/api/nope", "/auth/nope"])
async def test_api_and_auth_paths_stay_404(http: httpx.AsyncClient, path: str) -> None:
    response = await http.get(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")

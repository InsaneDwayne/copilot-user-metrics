# ruff: noqa: S105, S603 - a local demo: fixed demo secrets, our own subprocess
"""Regenerate the documentation screenshots in docs/images/ from fictional demo data.

Steps: recreate a separate demo database, migrate it, seed it (demo_data.py), start the API
with the built dashboard on a spare port, sign in as each persona by minting the session cookie
with the demo session secret, and capture every page in light and dark mode with Playwright.
Nothing talks to GitHub, and your dev database is left alone. With ``--as-of``, the data, the
API's clock and the browser's clock are all fixed, the font is served from fonts/ rather than the
network, and an image is only rewritten when its pixels change, so unchanged UI leaves
docs/images/ untouched.

Run from the repository root (see tools/screenshots/README.md):

    just screenshots                      # or, by hand:
    npm --prefix frontend run build
    uv run --directory backend --group screenshots python ../tools/screenshots/screenshots.py
"""

import argparse
import asyncio
import base64
import importlib.metadata
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

import psycopg
from itsdangerous import TimestampSigner
from pydantic import SecretStr

from copilot_metrics.shared.kernel import Clock

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserType, Route

sys.path.insert(0, str(Path(__file__).parent))
import demo_data

ROOT = Path(__file__).resolve().parents[2]
DEMO_DB = "copilot_demo"
# Only signs cookies for the throwaway demo API; never use it anywhere else.
SESSION_SECRET = "screenshots-only-not-a-secret-0123456789abcdef"
COOKIE_NAME = "copilot_session"
# The day the screenshots show. Fixed, so the same UI always gives the same images and the
# release check and the Screenshots workflow only report a change when the UI changed. Move it forward now and
# then (e.g. once a year); `--as-of now` shows today.
AS_OF = "2026-11-20"
# The theme loads Inter from Google Fonts, which may change it (or be unreachable) at any time.
# The capture serves this copy instead (Inter 4.1, the full variable font: every glyph the UI
# uses, so nothing falls back to the system's fonts) and blocks every other outside request.
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")
FONT_FILE = Path(__file__).parent / "fonts" / "InterVariable.woff2"
FONT_URL = "https://fonts.screenshots.invalid/InterVariable.woff2"
FONT_CSS = f"""@font-face {{
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  font-display: block;
  src: url("{FONT_URL}") format("woff2");
}}
"""
# Rendering that doesn't depend on the machine: grayscale text whatever the system's fontconfig
# says (Ubuntu turns on sub-pixel anti-aliasing, Debian doesn't), a fixed color profile, and
# Skia's portable code instead of the variant it picks for the CPU at runtime (GitHub's runners
# come with different CPUs, which shifted anti-aliased edges by a level or two). No partial
# raster: when a page re-renders after loading (e.g. the Sync page's polling), Chromium would
# otherwise redraw only the changed rectangle, and anti-aliased edges at its border came out
# differently depending on timing (the Admin tag on the Sync page, ~1 run in 6).
CHROMIUM_ARGS = [
    "--font-render-hinting=none",
    "--disable-lcd-text",
    "--force-color-profile=srgb",
    "--disable-skia-runtime-opts",
    "--disable-partial-raster",
]


@dataclass(frozen=True)
class Shot:
    name: str  # docs/images/<name>.png and <name>-dark.png
    path: str
    persona: str | None  # login from demo_data, or None for signed out
    full_page: bool = True


SHOTS = [
    Shot("signin", "/signin", None, full_page=False),
    Shot("my-usage", "/me", demo_data.MEMBER),
    Shot("my-activity", "/me/activity", demo_data.MEMBER),
    Shot("no-access", "/no-access", demo_data.OUTSIDER, full_page=False),
    Shot("admin-overview", "/admin", demo_data.ADMIN),
    Shot("admin-adoption", "/admin/adoption", demo_data.ADMIN),
    Shot("admin-members", "/admin/members", demo_data.ADMIN),
    Shot("admin-member-detail", f"/admin/members/{demo_data.MEMBER}", demo_data.ADMIN),
    Shot("admin-seats", "/admin/seats", demo_data.ADMIN),
    Shot("admin-team", "/admin/teams/web", demo_data.ADMIN),
    Shot("admin-sync", "/admin/sync", demo_data.ADMIN),
    Shot("reader-overview", "/admin", demo_data.READER),
]

ROLES = {
    demo_data.MEMBER: "member",
    demo_data.ADMIN: "admin",
    demo_data.READER: "org_reader",
    demo_data.OUTSIDER: "outsider",
}
NAMES = {
    demo_data.MEMBER: "Dana Developer",
    demo_data.ADMIN: "Olivia Owner",
    demo_data.READER: "Rui Reader",
    demo_data.OUTSIDER: "Pat Personal",
}


def with_database(url: str, database: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{database}"))


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set. Run this in the dev container, or set it (see tools/screenshots/README.md).")
    return value


def reset_database(admin_url: str, api_url: str, worker_url: str) -> None:
    """Drop and recreate the demo database. ``admin_url`` must be able to create databases."""
    api_role, worker_role = urlsplit(api_url).username, urlsplit(worker_url).username
    with psycopg.connect(admin_url, autocommit=True) as conn:
        owner = conn.execute("SELECT current_user").fetchone()[0]  # type: ignore[index]
        conn.execute(f'DROP DATABASE IF EXISTS "{DEMO_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{DEMO_DB}" OWNER "{owner}"')
        conn.execute(f'GRANT CONNECT ON DATABASE "{DEMO_DB}" TO "{api_role}", "{worker_role}"')


def app_env(**settings: str) -> dict[str, str]:
    """The environment without the dev stack's app settings, plus ``settings``."""
    prefixes = ("GITHUB_", "API_", "SESSION_", "ACCESS_", "SYNC_", "WORKER_", "DATABASE_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes)}
    return env | settings


def cli(*args: str) -> list[str]:
    """The backend's ``copilot-metrics`` command, from the environment running this script."""
    return [str(Path(sys.executable).parent / "copilot-metrics"), *args]


def user_ids() -> dict[str, int]:
    return {p.holder.login: p.holder.user_id for p in demo_data.people()} | {demo_data.OUTSIDER: 99_999}


class FixedClock(Clock):
    """The API's clock, stopped at ``--as-of``, so "this cycle" and "synced 9 minutes ago" match the data."""

    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at


@contextmanager
def running_api(api_url: str, port: int, static_dir: Path, now: datetime) -> Iterator[str]:
    """The API with the built dashboard, in a background thread of this process.

    Its settings are passed in rather than read from the environment, so the dev stack's
    .env and variables can't change what the screenshots show."""
    import uvicorn

    from copilot_metrics.api import create_app
    from copilot_metrics.settings import ApiSettings, GitHubSettings, SessionSettings, Settings

    base = f"http://127.0.0.1:{port}"
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        log_level="WARNING",
        github=GitHubSettings(org=demo_data.ORG, app_client_id="demo", app_client_secret=SecretStr("demo")),
        api=ApiSettings(database_url=api_url, public_url=base, static_dir=static_dir),  # type: ignore[arg-type]
        session=SessionSettings(secret=SecretStr(SESSION_SECRET), max_age_hours=12),
    )
    app = create_app(settings, clock=FixedClock(now))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                sys.exit("The demo API didn't start; see the output above.")
            time.sleep(0.1)
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def session_cookie(login: str, user_id: int, now: datetime) -> str:
    """The value Starlette's SessionMiddleware would set after signing in ``login`` at ``now``."""
    session = {
        "user": {
            "user_id": user_id,
            "login": login,
            "name": NAMES[login],
            "avatar_url": None,
            "role": ROLES[login],
            "signed_in_at": now.isoformat(),
        }
    }
    data = base64.b64encode(json.dumps(session).encode("utf-8"))
    return TimestampSigner(SESSION_SECRET).sign(data).decode("utf-8")


SYSTEM_BROWSERS = ("chromium", "chromium-browser", "google-chrome")


def launch(chromium: BrowserType, executable: str | None) -> Browser:
    """Playwright's own Chromium (in the dev container, the one baked into the image), else one
    installed on the system (e.g. Debian's ``chromium``, for networks that block Playwright's
    download host)."""
    from playwright.sync_api import Error

    if executable:
        return chromium.launch(executable_path=executable, args=CHROMIUM_ARGS)
    try:
        return chromium.launch(args=CHROMIUM_ARGS)
    except Error as e:
        if "Executable doesn't exist" not in str(e):
            raise
    for name in SYSTEM_BROWSERS:
        if path := shutil.which(name):
            print(f"  Playwright's Chromium isn't installed; using {path}")
            return chromium.launch(executable_path=path, args=CHROMIUM_ARGS)
    baked = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/nonexistent"))
    if found := sorted(p.name for p in baked.glob("chromium*")):
        import playwright

        browsers = json.loads((Path(playwright.__file__).parent / "driver/package/browsers.json").read_text())
        wanted = next(b["revision"] for b in browsers["browsers"] if b["name"] == "chromium")
        sys.exit(
            f"The browsers in {baked} ({', '.join(found)}) aren't the ones Playwright"
            f" {importlib.metadata.version('playwright')} needs (chromium-{wanted}). Set the"
            " image in .devcontainer/Dockerfile to mcr.microsoft.com/playwright/python at that"
            " version (Dependabot proposes it), then rebuild the dev container."
        )
    sys.exit("No browser found: run `just screenshots-setup` (see tools/screenshots/README.md).")


def offline(base: str, blocked: list[str]) -> Callable[[Route], None]:
    """Route handler: the demo API passes, Google Fonts gets the vendored Inter, the rest is blocked."""
    font = FONT_FILE.read_bytes()

    def handle(route: Route) -> None:
        url = route.request.url
        host = urlsplit(url).hostname or ""
        if url.startswith(base):
            route.continue_()
        elif url == FONT_URL:
            route.fulfill(body=font, content_type="font/woff2", headers={"Access-Control-Allow-Origin": "*"})
        elif host in FONT_HOSTS and urlsplit(url).path.startswith("/css"):
            route.fulfill(body=FONT_CSS, content_type="text/css")
        else:
            blocked.append(url)
            route.abort()

    return handle


# How far a pixel's color may drift (0-255 per channel) and still count as unchanged. Chromium
# doesn't rasterize every edge identically on every run: anti-aliased corners can come out a
# level or two apart. That's invisible; any real UI change (text, layout, colors) moves pixels
# by far more.
PIXEL_TOLERANCE = 8


def save_png(png: bytes, file: Path) -> str | None:
    """Write ``png`` to ``file`` unless the file already shows the same pixels (within
    ``PIXEL_TOLERANCE``); if written, returns what changed.

    Chromium's PNG encoding isn't byte-stable (same pixels, different bytes from run to run),
    so the image is compared by its pixels and re-encoded with Pillow, which is deterministic."""
    from PIL import Image, ImageChops

    new = Image.open(io.BytesIO(png)).convert("RGBA")
    reason = "new"
    if file.exists():
        with Image.open(file) as current:
            old = current.convert("RGBA")
        if old.size != new.size:
            reason = f"size {old.size[0]}x{old.size[1]} -> {new.size[0]}x{new.size[1]}"
        else:
            # Per pixel, the largest difference of any channel.
            r, g, b, a = ImageChops.difference(old, new).split()
            worst = ImageChops.lighter(ImageChops.lighter(r, g), ImageChops.lighter(b, a))
            counts = worst.histogram()  # pixels per difference, 0-255
            drift = max(d for d, n in enumerate(counts) if n)
            if drift <= PIXEL_TOLERANCE:
                return None
            pixels = sum(counts[PIXEL_TOLERANCE + 1 :])
            reason = f"{pixels} pixels differ, by up to {drift}"
    new.save(file, format="PNG", optimize=True)
    return reason


def capture(
    base: str,
    out: Path,
    shots: list[Shot],
    now: datetime,
    *,
    scale: float,
    width: int,
    height: int,
    executable: str | None,
) -> None:
    from playwright.sync_api import sync_playwright

    ids = user_ids()
    out.mkdir(parents=True, exist_ok=True)
    changed = 0
    with sync_playwright() as pw:
        browser = launch(pw.chromium, executable)
        try:
            for mode in ("light", "dark"):
                for shot in shots:
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        device_scale_factor=scale,
                        color_scheme=mode,
                        locale="en-US",
                        timezone_id="UTC",
                    )
                    blocked: list[str] = []
                    context.route("**/*", offline(base, blocked))
                    context.clock.set_fixed_time(now)  # the browser's clock matches the API's
                    # The header toggle's stored choice wins over the system preference.
                    context.add_init_script(f"localStorage.setItem('theme-mode', '{mode}')")
                    if shot.persona:
                        cookie = session_cookie(shot.persona, ids[shot.persona], now)
                        context.add_cookies([{"name": COOKIE_NAME, "value": cookie, "url": base}])
                    page = context.new_page()
                    page.goto(base + shot.path, wait_until="networkidle")
                    page.wait_for_function("!document.body.innerText.includes('Loading…')", timeout=15_000)
                    page.evaluate("document.fonts.ready")
                    if blocked:
                        sys.exit(f"{shot.path}: blocked requests outside the demo API: {', '.join(blocked)}")
                    if not page.evaluate("document.fonts.check('16px Inter')"):
                        sys.exit(f"{shot.path}: Inter didn't load.")
                    text = page.inner_text("body")
                    if "Couldn’t load this" in text:
                        sys.exit(f"{shot.path} as {shot.persona}: a section failed to load.")
                    expected = shot.path.split("?")[0]
                    if urlsplit(page.url).path != expected:
                        sys.exit(f"{shot.path} as {shot.persona}: redirected to {page.url}.")
                    file = out / (f"{shot.name}.png" if mode == "light" else f"{shot.name}-dark.png")
                    png = page.screenshot(full_page=shot.full_page, animations="disabled")
                    reason = save_png(png, file)
                    changed += reason is not None
                    shown = file.relative_to(ROOT) if file.is_relative_to(ROOT) else file
                    print(f"  {shown}{f'  (changed: {reason})' if reason else ''}")
                    context.close()
        finally:
            browser.close()
    print(f"{changed} of {2 * len(shots)} images changed.")


def as_of(value: str) -> datetime:
    """``2026-11-20`` (taken as 14:00 UTC), a full ISO time, or ``now``."""
    if value == "now":
        return datetime.now(UTC).replace(microsecond=0)
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(hour=14, tzinfo=UTC)
    at = datetime.fromisoformat(value)
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "images", help="output directory")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="only these shots, e.g. my-usage admin-overview")
    parser.add_argument("--scale", type=float, default=1, help="device pixel ratio (2 for retina-sharp images)")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--port", type=int, default=8100, help="port of the temporary demo API")
    parser.add_argument(
        "--browser",
        default=os.environ.get("SCREENSHOTS_BROWSER"),
        help="Chromium executable to use instead of Playwright's own (default: $SCREENSHOTS_BROWSER)",
    )
    parser.add_argument(
        "--as-of",
        type=as_of,
        default=AS_OF,
        metavar="DATE",
        help=f"pretend it is this day (14:00 UTC), time, or `now`: same date, same data, same images "
        f"(default: {AS_OF})",
    )
    parser.add_argument("--skip-seed", action="store_true", help="reuse the demo database from the last run")
    parser.add_argument(
        "--serve", action="store_true", help="seed and start the demo API, then wait (to look around by hand)"
    )
    args = parser.parse_args()

    shots = [s for s in SHOTS if not args.only or s.name in args.only]
    if args.only and len(shots) != len(args.only):
        sys.exit(f"Unknown shot name. Known: {', '.join(s.name for s in SHOTS)}")
    static_dir = ROOT / "frontend" / "dist"
    if not (static_dir / "index.html").exists():
        sys.exit("frontend/dist is missing: run `npm --prefix frontend run build` first.")

    # A role that may create databases: the dev container's DATABASE_URL is the Postgres superuser.
    owner_url = with_database(os.environ.get("DEMO_ADMIN_DATABASE_URL") or required_env("DATABASE_URL"), DEMO_DB)
    api_url = with_database(required_env("API_DATABASE_URL"), DEMO_DB)
    worker_url = with_database(required_env("WORKER_DATABASE_URL"), DEMO_DB)

    now = args.as_of
    with tempfile.TemporaryDirectory() as cwd:  # no .env files in reach of the migrations' settings
        if not args.skip_seed:
            print(f"Recreating the {DEMO_DB} database and seeding demo data ...")
            reset_database(with_database(owner_url, "postgres"), api_url, worker_url)
            env = app_env(DATABASE_URL=owner_url)
            subprocess.run(cli("migrate"), env=env, cwd=cwd, check=True)
            asyncio.run(demo_data.seed(worker_url, now))

        with running_api(api_url, args.port, static_dir, now) as base:
            if args.serve:
                print(f"Demo API on {base}, its clock stopped at {now:%Y-%m-%d %H:%M} UTC.")
                print(f"Sign-in cookies (name {COOKIE_NAME}):")
                ids = user_ids()
                for login, role in ROLES.items():
                    print(f"  {role:10} {session_cookie(login, ids[login], now)}")
                print("Ctrl+C to stop.")
                try:
                    while True:
                        time.sleep(3600)
                except KeyboardInterrupt:
                    return
            print(f"Capturing {len(shots)} pages in light and dark mode into {args.out} ...")
            capture(
                base,
                args.out,
                shots,
                now,
                scale=args.scale,
                width=args.width,
                height=args.height,
                executable=args.browser,
            )


if __name__ == "__main__":
    main()

"""Serves the built frontend from the API process (used by the Docker image)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from copilot_metrics.shared.errors import NotFound

# Everything outside /assets (index.html, the mounted theme/, favicon) keeps its URL across
# releases and edits, so browsers must not cache it heuristically: an edited theme then shows
# on the next reload. These files are small; /assets files are content-hashed by Vite and
# keep the default caching.
_REVALIDATE = {"Cache-Control": "no-cache"}


def mount_spa(app: FastAPI, root: Path) -> None:
    """Unknown paths fall back to index.html (client-side routing); API paths stay 404."""
    index = root / "index.html"
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "auth/")):
            raise NotFound("No such endpoint")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return FileResponse(candidate, headers=_REVALIDATE)
        return FileResponse(index, headers=_REVALIDATE)

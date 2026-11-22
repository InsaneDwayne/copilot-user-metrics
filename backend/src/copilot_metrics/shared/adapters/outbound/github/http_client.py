"""Plumbing shared by the two GitHub clients (sign-in and sync)."""

import httpx

from copilot_metrics.settings import GitHubSettings


def github_client(settings: GitHubSettings, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.api_url,
        timeout=settings.timeout_seconds,
        transport=transport,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.api_version,
            "User-Agent": "copilot-metrics-dashboard",
        },
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

"""GitHubOrg backed by a GitHub App installation token (read-only App permissions:
Administration, GitHub Copilot Business, Organization Copilot metrics, Members)."""

import asyncio
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import jwt

from copilot_metrics.settings import GitHubSettings
from copilot_metrics.shared.adapters.outbound.github.http_client import bearer
from copilot_metrics.shared.kernel import Frozen
from copilot_metrics.shared.metrics_record import OrgDayMetrics, UserDayMetrics, missing_fields
from copilot_metrics.sync.domain import (
    BudgetPage,
    CopilotBilling,
    CopilotSeat,
    CreditUsageItem,
    CreditUsageReport,
    GitHubBudget,
    ReportLinks,
    SeatsPage,
    UsageSummaryItem,
    UsageSummaryReport,
    UserTeamRecord,
)
from copilot_metrics.sync.ports import GitHubOrg

log = logging.getLogger(__name__)

_MAX_RATE_LIMIT_WAIT = 900.0
_RETRIES = 3


class _Installation(Frozen):
    id: int


class _InstallationToken(Frozen):
    token: str
    expires_at: datetime


class AppTokenProvider:
    """Mints a short-lived App JWT and swaps it for a cached installation token."""

    def __init__(self, settings: GitHubSettings, app_id: int, private_key: str, client: httpx.AsyncClient) -> None:
        self._org = settings.org
        self._app_id = app_id
        self._private_key = private_key
        self._client = client
        self._token: _InstallationToken | None = None
        self._lock = asyncio.Lock()

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": str(self._app_id)}
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def token(self) -> str:
        async with self._lock:
            if self._token and self._token.expires_at - datetime.now(UTC) > timedelta(minutes=5):
                return self._token.token
            app_auth = bearer(self._app_jwt())
            response = await self._client.get(f"/orgs/{self._org}/installation", headers=app_auth)
            response.raise_for_status()
            installation = _Installation.model_validate_json(response.content)
            response = await self._client.post(f"/app/installations/{installation.id}/access_tokens", headers=app_auth)
            response.raise_for_status()
            self._token = _InstallationToken.model_validate_json(response.content)
            return self._token.token


class GitHubOrgClient(GitHubOrg):
    def __init__(
        self,
        settings: GitHubSettings,
        tokens: AppTokenProvider,
        api: httpx.AsyncClient,
        downloads: httpx.AsyncClient,
    ) -> None:
        self._org = settings.org
        self._tokens = tokens
        self._api = api
        # Report links are pre-signed URLs on another host: never send the token there.
        self._downloads = downloads

    async def _get(
        self, url: str, params: dict[str, str | int] | None = None, allow: tuple[int, ...] = ()
    ) -> httpx.Response:
        """GET with rate-limit retries; raises on error statuses other than those in ``allow``."""
        for attempt in range(_RETRIES + 1):
            response = await self._api.get(url, params=params, headers=bearer(await self._tokens.token()))
            wait = _rate_limit_wait(response)
            if wait is None or attempt == _RETRIES:
                if response.status_code not in allow:
                    response.raise_for_status()
                return response
            log.warning("rate limited on %s, waiting %.0fs", url, wait)
            await asyncio.sleep(wait)
        raise AssertionError("unreachable")

    async def copilot_billing(self) -> CopilotBilling:
        response = await self._get(f"/orgs/{self._org}/copilot/billing")
        return CopilotBilling.model_validate_json(response.content)

    async def seats(self) -> list[CopilotSeat]:
        seats: list[CopilotSeat] = []
        url: str | None = f"/orgs/{self._org}/copilot/billing/seats"
        params: dict[str, str | int] | None = {"per_page": 100}
        while url:
            response = await self._get(url, params)
            seats.extend(SeatsPage.model_validate_json(response.content).seats)
            url = response.links.get("next", {}).get("url")
            params = None  # the next link carries its own query
        return seats

    async def credit_usage(self, day: date, login: str | None = None) -> list[CreditUsageItem]:
        return await self._credit_usage({"year": day.year, "month": day.month, "day": day.day}, login)

    async def monthly_credit_usage(self, year: int, month: int, login: str | None = None) -> list[CreditUsageItem]:
        return await self._credit_usage({"year": year, "month": month}, login)

    async def _credit_usage(self, params: dict[str, str | int], login: str | None) -> list[CreditUsageItem]:
        if login:
            params["user"] = login
        response = await self._get(f"/organizations/{self._org}/settings/billing/ai_credit/usage", params)
        return CreditUsageReport.model_validate_json(response.content).usage_items

    async def budgets(self, user: str | None = None) -> BudgetPage:
        merged: list[GitHubBudget] = []
        first: BudgetPage | None = None
        page = 1
        while True:
            params: dict[str, str | int] = {"per_page": 100, "page": page}
            if user:
                params["user"] = user
            response = await self._get(f"/organizations/{self._org}/settings/billing/budgets", params)
            current = BudgetPage.model_validate_json(response.content)
            first = first or current
            merged.extend(current.budgets)
            if not current.has_next_page or not current.budgets:
                break
            page += 1
        assert first is not None
        return first.model_copy(update={"budgets": merged, "has_next_page": False})

    async def usage_summary(self, year: int, month: int) -> list[UsageSummaryItem]:
        params: dict[str, str | int] = {"year": year, "month": month}
        response = await self._get(f"/organizations/{self._org}/settings/billing/usage/summary", params)
        return UsageSummaryReport.model_validate_json(response.content).usage_items

    async def _report_files(self, report: str, day: date) -> list[str]:
        """The day's report, as the text of each file GitHub links to; none if it has no report (yet)."""
        response = await self._get(
            f"/orgs/{self._org}/copilot/metrics/reports/{report}", {"day": day.isoformat()}, allow=(204, 404)
        )
        if response.status_code in (204, 404):
            return []
        files: list[str] = []
        for link in ReportLinks.model_validate_json(response.content).download_links:
            download = await self._downloads.get(link)
            download.raise_for_status()
            files.append(download.text)
        return files

    async def _report_lines(self, report: str, day: date) -> list[str]:
        """NDJSON reports: one record per non-empty line."""
        return [line for text in await self._report_files(report, day) for line in text.splitlines() if line.strip()]

    async def user_metrics(self, day: date) -> list[UserDayMetrics]:
        records = [UserDayMetrics.model_validate_json(line) for line in await self._report_lines("users-1-day", day)]
        _warn_on_format_change("users-1-day", day, records)
        return records

    async def user_teams(self, day: date) -> list[UserTeamRecord]:
        return [UserTeamRecord.model_validate_json(line) for line in await self._report_lines("user-teams-1-day", day)]

    async def org_metrics(self, day: date) -> list[OrgDayMetrics]:
        records = [
            OrgDayMetrics.model_validate(record)
            for text in await self._report_files("organization-1-day", day)
            for record in org_day_records(text)
        ]
        _warn_on_format_change("organization-1-day", day, records)
        return records


def _warn_on_format_change(report: str, day: date, records: list[UserDayMetrics] | list[OrgDayMetrics]) -> None:
    """The stored records keep the missing fields as zero, so say so while the cause is still visible."""
    missing, unknown = missing_fields(records)
    if missing:
        log.warning(
            "%s %s: no record has %s, the dashboard will show them as zero; fields not known to the model: %s",
            report,
            day,
            ", ".join(missing),
            ", ".join(unknown) or "none",
        )


def org_day_records(text: str) -> list[dict[str, Any]]:
    """The day records in one organization report file.

    GitHub documents a single JSON document, either ``{"day_totals": [...]}`` or one flat day;
    NDJSON (one of those per line) is accepted too, like the per-user reports.
    """
    try:
        documents = [json.loads(text)]
    except json.JSONDecodeError:
        documents = [json.loads(line) for line in text.splitlines() if line.strip()]
    records: list[dict[str, Any]] = []
    for doc in documents:
        if isinstance(doc, list):
            records.extend(d for d in doc if isinstance(d, dict))
        elif isinstance(doc, dict) and isinstance(doc.get("day_totals"), list):
            records.extend(d for d in doc["day_totals"] if isinstance(d, dict))
        elif isinstance(doc, dict) and "day" in doc:
            records.append(doc)
    return records


def _rate_limit_wait(response: httpx.Response) -> float | None:
    """Seconds to wait if GitHub rate-limited the request, else None."""
    if response.status_code not in (403, 429):
        return None
    if retry_after := response.headers.get("retry-after"):
        return min(float(retry_after), _MAX_RATE_LIMIT_WAIT)
    if response.headers.get("x-ratelimit-remaining") == "0":
        reset = float(response.headers.get("x-ratelimit-reset", time.time() + 60))
        return min(max(reset - time.time(), 1.0), _MAX_RATE_LIMIT_WAIT)
    return None

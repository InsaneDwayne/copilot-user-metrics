"""Metrics reports: download links and per-user team membership."""

from datetime import date

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from copilot_metrics.shared.kernel import Frozen


class ReportLinks(Frozen):
    download_links: list[str] = []
    report_day: date | None = None


class UserTeamRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    day: date
    user_id: int
    user_login: str
    # GitHub's report names it `slug`; the others are kept for older report versions.
    team_slug: str = Field(validation_alias=AliasChoices("slug", "team_slug", "team_name", "team"))

"""AI credits per day and model, and model calls and tokens from the usage metrics."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen, Period


class CreditRow(Frozen):
    """One stored row: a day and model, for one person or the whole org."""

    day: date
    model: str
    credits: Amount
    gross_usd: Amount
    included_usd: Amount
    billed_usd: Amount


class CreditTotals(Frozen):
    credits: Amount = ZERO
    gross_usd: Amount = ZERO
    included_usd: Amount = ZERO
    billed_usd: Amount = ZERO

    @classmethod
    def of(cls, rows: Iterable[CreditRow]) -> CreditTotals:
        rows = list(rows)
        return cls(
            credits=sum((r.credits for r in rows), ZERO),
            gross_usd=sum((r.gross_usd for r in rows), ZERO),
            included_usd=sum((r.included_usd for r in rows), ZERO),
            billed_usd=sum((r.billed_usd for r in rows), ZERO),
        )


class DailyCredits(Frozen):
    day: date
    credits: Amount
    gross_usd: Amount
    billed_usd: Amount


class ModelUsage(Frozen):
    model: str
    credits: Amount
    gross_usd: Amount
    billed_usd: Amount
    share: float  # 0..1 of the credits in the period


class Projection(Frozen):
    """Straight-line projection to the end of a period that contains today."""

    elapsed_days: int
    total_days: int
    daily_average: Amount
    projected_credits: Amount
    projected_gross_usd: Amount

    @classmethod
    def of(cls, totals: CreditTotals, period: Period, today: date) -> Projection | None:
        if not period.contains(today):
            return None
        elapsed = (today - period.start).days + 1
        factor = 1 + Decimal((period.end - today).days) / elapsed
        return cls(
            elapsed_days=elapsed,
            total_days=period.days,
            daily_average=totals.credits / elapsed,
            projected_credits=totals.credits * factor,
            projected_gross_usd=totals.gross_usd * factor,
        )


def daily_series(rows: Iterable[CreditRow], period: Period, today: date) -> list[DailyCredits]:
    """One point per day from the period start through today (or the period end)."""
    per_day: defaultdict[date, list[CreditRow]] = defaultdict(list)
    for row in rows:
        per_day[row.day].append(row)
    series = []
    for d in period.each_day(until=today):
        t = CreditTotals.of(per_day[d])
        series.append(DailyCredits(day=d, credits=t.credits, gross_usd=t.gross_usd, billed_usd=t.billed_usd))
    return series


def model_breakdown(rows: Iterable[CreditRow]) -> list[ModelUsage]:
    by_model: defaultdict[str, list[CreditRow]] = defaultdict(list)
    for row in rows:
        by_model[row.model].append(row)
    totals = {model: CreditTotals.of(group) for model, group in by_model.items()}
    all_credits = sum((t.credits for t in totals.values()), ZERO) or Decimal(1)
    usage = [
        ModelUsage(
            model=m,
            credits=t.credits,
            gross_usd=t.gross_usd,
            billed_usd=t.billed_usd,
            share=float(t.credits / all_credits),
        )
        for m, t in totals.items()
        if t.credits > 0
    ]
    return sorted(usage, key=lambda u: u.credits, reverse=True)


class ModelCallsRow(Frozen):
    """A day's calls for one client and model, as the usage metrics report them."""

    day: date
    client: str | None
    model: str | None
    custom_model: bool  # GitHub's is_custom_enterprise_model
    requests: int
    prompt_tokens: int
    output_tokens: int


class ModelTokens(Frozen):
    """A day's model calls and tokens for one model, from the usage metrics
    (``totals_by_client[].totals_by_model[]``, summed across clients).

    Model names are GitHub's metrics names, which need not match the billing names on
    credit rows. Cached tokens are not in the metrics, only in the emailed AI usage report.
    """

    day: date
    model: str
    requests: int
    prompt_tokens: int
    output_tokens: int

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens


# GitHub's client keys as people say them; others are humanised.
_CLIENTS = {
    "vscode": "VS Code",
    "visualstudio": "Visual Studio",
    "jetbrains": "JetBrains",
    "xcode": "Xcode",
    "eclipse": "Eclipse",
    "neovim": "Neovim",
    "cli": "Copilot CLI",
    "cloud_agent": "cloud agent",
    "github_web": "github.com",
    "opencode": "OpenCode",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "other": "other tools",
}
# What GitHub writes when it can't name the model.
_UNNAMED = {"", "unknown"}


def client_label(client: str | None) -> str:
    if not client:
        return "unknown client"
    return _CLIENTS.get(client.lower(), client.replace("_", " "))


def model_label(row: ModelCallsRow) -> str:
    """The model's name, or for calls GitHub reports as "unknown", where they came from.

    GitHub documents two causes: code review never reports its model, and enterprise custom
    models it can't match to a known name. Anything else is named by its client, so the
    unnamed calls of different tools don't merge into one "unknown" row.
    """
    if row.model and row.model.strip().lower() not in _UNNAMED:
        return row.model
    if row.client == "code_review":
        return "Code review (model not reported)"
    if row.custom_model:
        return "Custom enterprise model (unmatched)"
    return f"Unidentified model · {client_label(row.client)}"


def model_tokens(rows: Iterable[ModelCallsRow]) -> list[ModelTokens]:
    """Calls per day and model across clients, named as above. Oldest day first; within a
    day, most tokens first. Rows without any use are left out."""
    sums: defaultdict[tuple[date, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        s = sums[(r.day, model_label(r))]
        s[0] += r.requests
        s[1] += r.prompt_tokens
        s[2] += r.output_tokens
    merged = [
        ModelTokens(day=day, model=model, requests=req, prompt_tokens=prompt, output_tokens=out)
        for (day, model), (req, prompt, out) in sums.items()
    ]
    used = (m for m in merged if m.requests or m.tokens)
    return sorted(used, key=lambda m: (m.day, -m.tokens, -m.requests, m.model))

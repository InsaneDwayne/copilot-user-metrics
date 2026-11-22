"""Write-side domain: what GitHub returns and how it becomes stored rows.

Response models ignore unknown fields so additions on GitHub's side don't
break the sync. Billing uses camelCase on the wire (``wire.CamelModel``).

One module per area; this package re-exports their public names.
"""

from copilot_metrics.sync.domain.budgets import (
    BudgetPage,
    BudgetRecord,
    EffectiveBudget,
    GitHubBudget,
    budget_for_user,
    org_budgets,
)
from copilot_metrics.sync.domain.catch_up import by_month, days_to_catch_up
from copilot_metrics.sync.domain.control import (
    SYNC_TASKS,
    QueuedJob,
    SyncAction,
    SyncControlStatus,
    SyncRequest,
    SyncTarget,
    TargetQueue,
    stop_outcome,
    target_queues,
)
from copilot_metrics.sync.domain.credits import (
    UNKNOWN_MODEL,
    CreditUsageItem,
    CreditUsageReport,
    ModelCredits,
    credits_by_model,
)
from copilot_metrics.sync.domain.reports import ReportLinks, UserTeamRecord
from copilot_metrics.sync.domain.seats import (
    AssigningTeam,
    CopilotBilling,
    CopilotSeat,
    SeatAssignee,
    SeatBreakdown,
    SeatHolder,
    SeatsPage,
)
from copilot_metrics.sync.domain.usage_summary import SeatCostRecord, UsageSummaryItem, UsageSummaryReport, seat_cost

__all__ = [
    "SYNC_TASKS",
    "UNKNOWN_MODEL",
    "AssigningTeam",
    "BudgetPage",
    "BudgetRecord",
    "CopilotBilling",
    "CopilotSeat",
    "CreditUsageItem",
    "CreditUsageReport",
    "EffectiveBudget",
    "GitHubBudget",
    "ModelCredits",
    "QueuedJob",
    "ReportLinks",
    "SeatAssignee",
    "SeatBreakdown",
    "SeatCostRecord",
    "SeatHolder",
    "SeatsPage",
    "SyncAction",
    "SyncControlStatus",
    "SyncRequest",
    "SyncTarget",
    "TargetQueue",
    "UsageSummaryItem",
    "UsageSummaryReport",
    "UserTeamRecord",
    "budget_for_user",
    "by_month",
    "credits_by_model",
    "days_to_catch_up",
    "org_budgets",
    "seat_cost",
    "stop_outcome",
    "target_queues",
]

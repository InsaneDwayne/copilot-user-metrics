from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from copilot_metrics.shared.kernel import Page, PageRequest, Period
from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.usage import domain

NOV = Period.cycle_of(date(2026, 11, 9))
TODAY = date(2026, 11, 9)


def row(day: int, model: str, credits: float, billed: float = 0.0) -> domain.CreditRow:
    return domain.CreditRow(
        day=date(2026, 11, day),
        model=model,
        credits=credits,
        gross_usd=credits / 100,
        included_usd=credits / 100 - billed,
        billed_usd=billed,
    )


def test_cycle_is_the_calendar_month() -> None:
    assert Period(start=date(2026, 11, 1), end=date(2026, 11, 30)) == NOV
    assert Period.cycle_of(date(2028, 2, 10)).end == date(2028, 2, 29)


def test_period_rejects_reversed_range() -> None:
    with pytest.raises(ValueError, match="before its start"):
        Period(start=date(2026, 11, 2), end=date(2026, 11, 1))


def totals(credits: float) -> domain.CreditTotals:
    return domain.CreditTotals(credits=credits, gross_usd=credits / 100)


def budget(amount: float, consumed: float, scope: str = "user") -> domain.Budget:
    return domain.Budget(
        id="b1",
        scope=scope,
        sku="ai_credits",
        amount_usd=amount,
        consumed_usd=consumed,
        prevent_further_usage=True,
        synced_at=datetime(2026, 11, 9, tzinfo=UTC),
    )


def test_projection_extrapolates_credits_and_dollars_to_cycle_end() -> None:
    projection = domain.Projection.of(totals(900.0), NOV, TODAY)
    assert projection is not None
    assert projection.elapsed_days == 9
    assert projection.daily_average == 100.0
    assert projection.projected_credits == pytest.approx(3000.0)
    assert projection.projected_gross_usd == pytest.approx(30.0)


def test_no_projection_for_closed_period() -> None:
    assert domain.Projection.of(totals(900.0), Period.cycle_of(date(2026, 10, 1)), TODAY) is None


def test_summary_fills_every_day_up_to_today_with_github_amounts() -> None:
    rows = [row(1, "A", 100, billed=0.5), row(1, "B", 50), row(5, "A", 200)]
    summary = domain.summarize(rows, NOV, TODAY, budget(50, 12))
    assert [d.credits for d in summary.daily] == [150, 0, 0, 0, 200, 0, 0, 0, 0]
    assert summary.daily[0].billed_usd == 0.5
    assert summary.totals.credits == 350
    assert summary.budget is not None
    assert summary.budget.consumed_usd == 12


def test_budget_is_only_shown_for_the_current_cycle() -> None:
    october = Period.cycle_of(date(2026, 10, 1))
    assert domain.summarize([], october, TODAY, budget(50, 12)).budget is None


def test_model_breakdown_sorted_with_shares() -> None:
    models = domain.model_breakdown([row(1, "A", 100), row(2, "B", 300), row(3, "A", 100), row(4, "Z", 0)])
    assert [(m.model, m.share) for m in models] == [("B", 0.6), ("A", 0.4)]


SEATS = domain.SeatSummary(
    total=48, active_this_cycle=43, inactive_this_cycle=5, pending_cancellation=0, synced_at=datetime.now(UTC)
)
SEAT_COST = domain.SeatCost(month=date(2026, 11, 1), seats=48, price_per_seat_usd=19, gross_usd=912, net_usd=912)


def test_org_summary_uses_github_budgets_and_seat_cost() -> None:
    org = domain.org_summary([row(1, "A", 900)], NOV, TODAY, SEATS, [budget(500, 40, "organization")], SEAT_COST)
    assert (org.seats, org.active_seats, org.totals.credits) == (48, 43, Decimal(900))
    assert org.budgets[0].amount_usd == 500
    assert org.seat_cost == SEAT_COST


def test_org_summary_drops_month_bound_figures_for_custom_ranges() -> None:
    custom = Period(start=date(2026, 10, 15), end=date(2026, 10, 31))
    org = domain.org_summary([], custom, TODAY, SEATS, [budget(500, 40, "organization")], SEAT_COST)
    assert org.budgets == []
    assert org.seat_cost is None


def test_activity_summary_aggregates_breakdowns() -> None:
    day = {
        "day": "2026-11-02",
        "user_id": 1,
        "user_login": "a",
        "user_initiated_interaction_count": 5,
        "code_generation_activity_count": 10,
        "code_acceptance_activity_count": 3,
        "loc_added_sum": 40,
        "used_cli": True,
        "totals_by_feature": [{"feature": "chat_panel_agent_mode", "user_initiated_interaction_count": 4}],
        "totals_by_language_feature": [
            {
                "language": "python",
                "code_generation_activity_count": 10,
                "code_acceptance_activity_count": 3,
                "loc_added_sum": 40,
            }
        ],
        "totals_by_ide": [{"ide": "vscode", "user_initiated_interaction_count": 5}],
        "totals_by_skill": [
            {"skill": "code-review", "interaction_count": 2},
            {"skill": "other", "interaction_count": 3},
            {"skill": "unused", "interaction_count": 0},
        ],
        "some_future_field": {"kept": True},
    }
    record = UserDayMetrics.model_validate(day)
    summary = domain.summarize_activity([record], NOV, TODAY, data_through=date(2026, 11, 8))
    assert summary.active_days == 1
    assert summary.elapsed_days == 8
    assert summary.acceptance_rate == pytest.approx(0.3)
    assert summary.top_ide == "vscode"
    assert summary.features == [domain.NamedCount(name="chat_panel_agent_mode", count=4)]
    assert summary.skills == [domain.NamedCount(name="other", count=3), domain.NamedCount(name="code-review", count=2)]
    assert summary.languages[0].language == "python"
    assert next(s for s in summary.surfaces if s.surface is domain.Surface.CLI).days == 1
    assert record.model_dump()["some_future_field"] == {"kept": True}


def member(login: str, last_active_days_ago: int | None, teams: list[str], credits: float) -> domain.MemberRow:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    return domain.MemberRow(
        user_id=hash(login),
        login=login,
        avatar_url=None,
        assigned_at=now - timedelta(days=100),
        ended_at=None,
        last_activity_at=None if last_active_days_ago is None else now - timedelta(days=last_active_days_ago),
        last_activity_editor=None,
        teams=teams,
        credits=credits,
        gross_usd=credits / 100,
        top_model=None,
        generations=10,
        acceptances=5,
    )


def test_seat_overview_buckets_idle_seats() -> None:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    rows = [member("a", 1, [], 10), member("b", 20, [], 0), member("c", None, [], 0)]
    overview = domain.seat_overview(rows, now, SEAT_COST)
    assert overview.seat_cost == SEAT_COST
    assert (overview.assigned, overview.active, overview.inactive, overview.never_used) == (3, 1, 1, 1)
    assert [s.login for s in overview.idle.items] == ["c", "b"]
    assert (overview.reclaimable, overview.reclaimable_usd) == (2, Decimal(38))


def test_seat_overview_idle_threshold_and_pending_cancellations() -> None:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    pending = member("p", 40, [], 0).model_copy(update={"pending_cancellation_date": date(2026, 11, 30)})
    new = member("new", None, [], 0).model_copy(update={"assigned_at": now - timedelta(days=3)})
    rows = [member("a", 1, [], 10), member("b", 20, [], 0), member("c", None, [], 0), pending, new]
    week = domain.seat_overview(rows, now, SEAT_COST)
    # A seat assigned 3 days ago and not used yet is too new to call idle.
    assert (week.active, week.inactive, week.never_used, week.recently_assigned) == (1, 2, 1, 1)
    assert (week.pending_cancellation, week.reclaimable, week.reclaimable_usd) == (1, 2, Decimal(38))
    assert [s.login for s in week.idle.items] == ["c", "b", "p"]  # pending cancellation last
    month = domain.seat_overview(rows, now, None, idle_after_days=30)
    assert month.idle_after_days == 30
    assert [s.login for s in month.idle.items] == ["c", "p"]
    assert (month.active, month.recently_assigned, month.reclaimable, month.reclaimable_usd) == (2, 1, 1, None)


def test_filter_members_returns_every_match_in_page_order() -> None:
    rows = [member(f"m{i}", 1, ["t"] if i % 2 else [], 100 - i) for i in range(30)]
    usage = domain.member_usage(rows, [], NOV, TODAY)
    query = domain.MemberQuery(team="t")
    every = domain.filter_members(usage, query)
    assert len(every) == 15
    page = domain.member_page(usage, query, PageRequest(page=1, size=10))
    assert [m.login for m in every[:10]] == [m.login for m in page.items]


def test_seat_overview_leaves_out_ended_seats() -> None:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    ended = member("gone", None, [], 0).model_copy(update={"ended_at": now - timedelta(days=2)})
    assert domain.seat_overview([member("a", 1, [], 10), ended], now, None).assigned == 1


def test_members_carry_their_budget_and_share() -> None:
    rows = [member("a", 1, [], 300), member("b", 1, [], 100)]
    budgets = [domain.UserBudget(user_id=rows[0].user_id, budget=budget(50, 10))]
    usage = domain.member_usage(rows, budgets, NOV, TODAY)
    assert [(m.login, m.share) for m in usage] == [("a", 0.75), ("b", 0.25)]
    assert usage[0].budget is not None
    assert usage[1].budget is None
    past = domain.member_usage(rows, budgets, Period.cycle_of(date(2026, 10, 1)), TODAY)
    assert all(m.budget is None for m in past)


def test_page_slices_and_clamps_past_the_end() -> None:
    rows = list(range(1, 8))
    second = Page[int].of(rows, PageRequest(page=2, size=3))
    assert (second.items, second.total, second.page, second.pages) == ([4, 5, 6], 7, 2, 3)
    assert Page[int].of(rows, PageRequest(page=9, size=3)).items == [7]
    empty = Page[int].of([], PageRequest(page=4, size=3))
    assert (empty.items, empty.page, empty.pages) == ([], 1, 1)


def test_page_request_bounds() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        PageRequest(page=0)
    with pytest.raises(ValueError, match="less than or equal to 100"):
        PageRequest(size=101)


def usage_of(*specs: tuple[str, list[str], float, domain.Budget | None]) -> list[domain.MemberUsage]:
    rows = [member(login, 1, teams, credits) for login, teams, credits, _ in specs]
    budgets = [domain.UserBudget(user_id=r.user_id, budget=b) for r, (*_, b) in zip(rows, specs, strict=True) if b]
    return domain.member_usage(rows, budgets, NOV, TODAY)


def test_member_page_filters_by_team_and_login_and_counts_before_filtering() -> None:
    usage = usage_of(("Ann", ["web"], 30, None), ("bob", ["web", "ops"], 20, None), ("cat", ["ops"], 10, None))
    web = domain.member_page(usage, domain.MemberQuery(team="web"), PageRequest())
    assert [m.login for m in web.items] == ["Ann", "bob"]
    assert (web.total, web.members, web.teams) == (2, 3, ["ops", "web"])
    found = domain.member_page(usage, domain.MemberQuery(login=" an "), PageRequest())
    assert [m.login for m in found.items] == ["Ann"]


def test_member_page_orders_by_budget_used_with_unbudgeted_last() -> None:
    usage = usage_of(
        ("none", [], 99, None),
        ("half", [], 10, budget(100, 50)),
        ("over", [], 5, budget(10, 12)),
    )
    page = domain.member_page(usage, domain.MemberQuery(sort=domain.MemberSort.BUDGET), PageRequest())
    assert [m.login for m in page.items] == ["over", "half", "none"]


def test_member_pages_do_not_overlap_when_credits_tie() -> None:
    usage = usage_of(*[(login, [], 0, None) for login in ["e", "b", "d", "a", "c"]])
    pages = [domain.member_page(usage, domain.MemberQuery(), PageRequest(page=n, size=2)) for n in (1, 2, 3)]
    assert [m.login for p in pages for m in p.items] == ["a", "b", "c", "d", "e"]


def test_teams_count_members_in_each_team() -> None:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    rows = [member("a", 1, ["x", "y"], 100), member("b", 30, ["x"], 50)]
    teams = domain.team_usage(rows, [domain.TeamModelCredits(team="x", model="M", credits=1)], now)
    x = next(t for t in teams if t.team == "x")
    assert (x.seats, x.active_7d, x.credits, x.top_model, x.acceptance_rate) == (2, 1, Decimal(150), "M", 0.5)


def calls(
    day: int, client: str | None, model: str | None, requests: int, prompt: int, custom: bool = False
) -> domain.ModelCallsRow:
    return domain.ModelCallsRow(
        day=date(2026, 11, day),
        client=client,
        model=model,
        custom_model=custom,
        requests=requests,
        prompt_tokens=prompt,
        output_tokens=0,
    )


def test_model_tokens_merge_clients_by_day_then_tokens_and_drop_unused() -> None:
    rows = [
        calls(4, "vscode", "late", 1, 1),
        calls(3, "vscode", "cheap", 60, 300_000),
        calls(3, "opencode", "cheap", 30, 200_000),
        calls(3, "vscode", "idle", 0, 0),
        calls(3, "vscode", "big", 5, 900_000),
    ]
    tokens = domain.model_tokens(rows)
    assert [(t.day.day, t.model, t.requests) for t in tokens] == [(3, "big", 5), (3, "cheap", 90), (4, "late", 1)]


def test_unknown_models_are_named_by_where_they_came_from() -> None:
    rows = [
        calls(3, "code_review", "unknown", 4, 400),
        calls(3, "vscode", "unknown", 2, 300, custom=True),
        calls(3, "opencode", "unknown", 3, 200),
        calls(3, "opencode", None, 1, 100),
        calls(3, "vscode", "Unknown", 1, 50),
        calls(3, "some_new_tool", "", 1, 10),
    ]
    assert {t.model: t.requests for t in domain.model_tokens(rows)} == {
        "Code review (model not reported)": 4,
        "Custom enterprise model (unmatched)": 2,
        "Unidentified model · OpenCode": 4,
        "Unidentified model · VS Code": 1,
        "Unidentified model · some new tool": 1,
    }


def test_metrics_record_reads_per_client_model_tokens() -> None:
    record = UserDayMetrics.model_validate(
        {
            "day": "2026-11-03",
            "user_id": 1,
            "user_login": "a",
            "totals_by_client": [
                {
                    "client": "vscode",
                    "totals_by_model": [
                        {"model": "gpt-5-mini", "request_count": 3, "token_usage": {"prompt_tokens_sum": 10}}
                    ],
                }
            ],
        }
    )
    model = record.totals_by_client[0].totals_by_model[0]
    assert (model.model, model.request_count, model.token_usage.prompt_tokens_sum) == ("gpt-5-mini", 3, 10)
    assert model.token_usage.output_tokens_sum == 0


# ---------------------------------------------------------------- adoption


def metrics(day: int, **fields: object) -> UserDayMetrics:
    return UserDayMetrics.model_validate({"day": f"2026-11-{day:02d}", "user_id": 1, "user_login": "a", **fields})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            {"phase_number": 2, "phase": "Phase 2", "version": "v1"},
            domain.AdoptionPhase(number=2, label="Phase 2", version="v1"),
        ),
        ({"phase_number": 0, "phase": "No Cohort"}, domain.AdoptionPhase(number=0, label="No Cohort")),
        ({"phase_number": "2", "phase": "Phase 2"}, None),
        ({"phase_number": True, "phase": "Phase 1"}, None),
        ({"phase_number": 1}, None),
        ("Phase 1", None),
        (None, None),
    ],
)
def test_adoption_phase_is_parsed_leniently(value: object, expected: domain.AdoptionPhase | None) -> None:
    assert domain.AdoptionPhase.parse(value) == expected


def test_activity_takes_the_latest_reported_phase_and_counts_surface_only_days() -> None:
    days = [
        metrics(3, user_initiated_interaction_count=2, ai_adoption_phase={"phase_number": 1, "phase": "Phase 1"}),
        metrics(5, used_cloud_agent=True, ai_adoption_phase={"phase_number": 2, "phase": "Phase 2"}),
        metrics(6, used_chat=True, ai_adoption_phase="garbage"),
        metrics(7),  # a record without any activity
    ]
    summary = domain.summarize_activity(days, NOV, TODAY, data_through=date(2026, 11, 8))
    assert summary.adoption_phase == domain.AdoptionPhase(number=2, label="Phase 2")
    assert summary.active_days == 3
    surfaces = {s.surface: s.days for s in summary.surfaces}
    assert (surfaces[domain.Surface.CHAT], surfaces[domain.Surface.CLOUD_AGENT]) == (1, 1)
    # Stored records keep GitHub's object as it came.
    assert days[2].model_dump()["ai_adoption_phase"] == "garbage"


@pytest.mark.parametrize(("days", "segment"), [(0, "none"), (1, "occasional"), (6, "occasional"), (7, "regular")])
def test_segments_by_active_days(days: int, segment: str) -> None:
    assert domain.segment_of(days) == segment


def active(login: str, active_days: int, credits: float = 0, teams: list[str] | None = None) -> domain.MemberRow:
    return member(login, 1, teams or [], credits).model_copy(update={"active_days": active_days})


def test_member_rows_parse_the_stored_phase() -> None:
    row = domain.MemberRow.model_validate(
        {**member("a", 1, [], 0).model_dump(), "adoption_phase": {"phase_number": 3, "phase": "Phase 3"}}
    )
    assert row.adoption_phase == domain.AdoptionPhase(number=3, label="Phase 3")
    bad = domain.MemberRow.model_validate({**member("a", 1, [], 0).model_dump(), "adoption_phase": {"phase": 3}})
    assert bad.adoption_phase is None


def test_member_page_filters_by_segment_and_sorts_by_active_days() -> None:
    rows = [active("idle", 0, 50, ["web"]), active("some", 3, 10, ["web"]), active("lots", 12, 5, ["ops"])]
    usage = domain.member_usage(rows, [], NOV, TODAY)
    assert [m.segment for m in usage] == ["none", "occasional", "regular"]
    assert usage[0].acceptance_rate == 0.5

    by_days = domain.member_page(usage, domain.MemberQuery(sort=domain.MemberSort.ACTIVE_DAYS), PageRequest())
    assert [m.login for m in by_days.items] == ["lots", "some", "idle"]

    idle_web = domain.member_page(
        usage, domain.MemberQuery(team="web", segment=domain.ActivitySegment.NONE), PageRequest()
    )
    assert [m.login for m in idle_web.items] == ["idle"]
    # Segment counts follow the team filter, not the segment filter.
    assert [(s.segment, s.members) for s in idle_web.segments] == [("none", 1), ("occasional", 1), ("regular", 0)]


def day_row(user_id: int, day: date, **flags: object) -> domain.ActivityDayRow:
    values: dict[str, object] = {
        "prompts": 0,
        "generations": 0,
        "acceptances": 0,
        "loc_suggested": 0,
        "loc_added": 0,
        **{f"used_{s}": False for s in ("chat", "agent", "cli", "cloud_agent", "app", "review")},
    }
    values.update(flags)
    return domain.ActivityDayRow.model_validate({"user_id": user_id, "day": day, **values})


def test_org_adoption_counts_rolling_active_people_from_before_the_period() -> None:
    oct_28 = date(2026, 10, 28)
    days = [
        day_row(1, oct_28, prompts=3),  # before the period: only in the rolling counts
        day_row(2, date(2026, 11, 1), generations=4, acceptances=1, loc_added=10),
        day_row(2, date(2026, 11, 2), used_review=True),
        day_row(3, date(2026, 11, 2), used_chat=True, prompts=2),
        day_row(4, date(2026, 11, 2)),  # a record without activity
    ]
    members = [
        active("a", 0).model_copy(update={"adoption_phase": domain.AdoptionPhase(number=2, label="Phase 2")}),
        active("b", 2).model_copy(update={"adoption_phase": domain.AdoptionPhase(number=0, label="No Cohort")}),
        active("c", 1),
    ]
    breakdown = domain.ActivityBreakdown(
        features=[
            domain.FeatureUse(name="code_completion", users=1, prompts=0),
            domain.FeatureUse(name="chat_panel_ask_mode", users=2, prompts=7),
            domain.FeatureUse(name="unused", users=0, prompts=0),
        ],
        languages=[domain.LanguageTotals(language="go", users=1, loc_added=10, generations=4, acceptances=1)],
        ides=[domain.IdeUse(ide="vscode", users=2), domain.IdeUse(ide="none", users=0)],
        skills=[
            domain.SkillUse(name="docs", users=1, invocations=9),
            domain.SkillUse(name="code-review", users=2, invocations=3),
            domain.SkillUse(name="unused", users=0, invocations=0),
        ],
    )
    org = domain.org_adoption(days, breakdown, members, NOV, TODAY, data_through=date(2026, 11, 3))

    assert [(d.day.day, d.active_users, d.active_7d, d.active_28d) for d in org.daily] == [
        (1, 1, 2, 2),
        (2, 2, 3, 3),
        (3, 0, 3, 3),
    ]
    assert org.daily[0].acceptance_rate == 0.25
    assert (org.seats, org.active_users, org.prompts, org.loc_added) == (3, 2, 2, 10)
    assert org.average_daily_active == 1.0
    surfaces = {s.surface: s.users for s in org.surfaces}
    assert (surfaces[domain.Surface.CHAT], surfaces[domain.Surface.CODE_REVIEW], surfaces[domain.Surface.CLI]) == (
        1,
        1,
        0,
    )
    assert [(s.segment, s.members) for s in org.segments] == [("none", 1), ("occasional", 2), ("regular", 0)]
    assert [(p.phase.label if p.phase else None, p.members) for p in org.phases] == [
        ("No Cohort", 1),
        ("Phase 2", 1),
        (None, 1),
    ]
    assert [f.name for f in org.features] == ["chat_panel_ask_mode", "code_completion"]
    assert org.languages[0].acceptance_rate == 0.25
    assert [i.ide for i in org.ides] == ["vscode"]
    assert [s.name for s in org.skills] == ["code-review", "docs"]


def test_org_adoption_without_metrics_has_no_series() -> None:
    org = domain.org_adoption([], domain.ActivityBreakdown(features=[], languages=[], ides=[]), [], NOV, TODAY, None)
    assert (org.daily, org.average_daily_active, org.acceptance_rate, org.phases) == ([], None, None, [])


def test_exports_flatten_members_and_idle_seats() -> None:
    now = datetime(2026, 11, 9, 12, tzinfo=UTC)
    row = member("a", 40, ["core", "web"], 10).model_copy(
        update={"adoption_phase": domain.AdoptionPhase(number=2, label="Phase 2", version=None), "active_days": 3}
    )
    (exported,) = domain.member_export(domain.member_usage([row], [], NOV, TODAY))
    assert (exported.teams, exported.adoption_phase, exported.activity, exported.share) == (
        "core; web",
        "Phase 2",
        domain.ActivitySegment.OCCASIONAL,
        1,
    )
    (seat,) = domain.idle_seat_export(domain.idle_seats([row], now, 30))
    assert (seat.login, seat.teams, seat.status, seat.inactive_days) == ("a", "core; web", "inactive", 40)


def test_code_changes_split_agent_from_person_guided_lines() -> None:
    record = UserDayMetrics.model_validate(
        {
            "day": "2026-11-02",
            "user_id": 1,
            "user_login": "a",
            "totals_by_feature": [
                {"feature": "agent_edit", "loc_added_sum": 70, "loc_deleted_sum": 10},
                {"feature": "code_completion", "loc_suggested_to_add_sum": 50, "loc_added_sum": 20},
                {"feature": "chat_panel_ask_mode", "user_initiated_interaction_count": 3},  # no lines: left out
            ],
            "totals_by_model_feature": [
                {"model": "m1", "feature": "agent_edit", "loc_added_sum": 70, "loc_deleted_sum": 10},
                {"model": "m2", "feature": "chat_panel_ask_mode", "user_initiated_interaction_count": 3},
            ],
            "totals_by_language_model": [{"language": "go", "model": "m1", "code_generation_activity_count": 2}],
        }
    )
    summary = domain.summarize_activity([record, record], NOV, TODAY, data_through=date(2026, 11, 8))
    changes = summary.code_changes
    assert [(c.feature, c.agent, c.loc_added) for c in changes.by_feature] == [
        ("agent_edit", True, 140),
        ("code_completion", False, 40),
    ]
    assert (changes.loc_added, changes.loc_deleted, changes.agent_loc_changed) == (180, 20, 160)
    assert changes.agent_share == pytest.approx(0.8)
    assert [(m.model, m.feature, m.loc_changed, m.prompts) for m in summary.model_features] == [
        ("m1", "agent_edit", 160, 0),
        ("m2", "chat_panel_ask_mode", 0, 6),
    ]
    assert [(lm.language, lm.generations) for lm in summary.language_models] == [("go", 4)]
    assert domain.code_changes([]).agent_share is None


def test_model_matrices_keep_the_most_used_models_and_languages() -> None:
    cells = [
        domain.ModelFeatureUse(model=f"m{i}", feature="chat", prompts=i, generations=0, loc_changed=0)
        for i in range(1, domain.TOP_MODELS + 3)
    ]
    kept = domain.model_feature_matrix(cells)
    assert len(kept) == domain.TOP_MODELS
    assert kept[0].model == f"m{domain.TOP_MODELS + 2}"
    languages = [
        domain.LanguageModelUse(language=f"l{i}", model="m", generations=i, acceptances=0, loc_changed=0)
        for i in range(domain.TOP_LANGUAGES + 2)  # l0 has no activity at all
    ]
    assert {r.language for r in domain.language_model_matrix(languages)} == {
        f"l{i}" for i in range(2, domain.TOP_LANGUAGES + 2)
    }


def test_amounts_are_exact_in_python_and_plain_numbers_in_json() -> None:
    cents = [row(1, "A", 0.1), row(2, "A", 0.2)]  # 0.1 + 0.2 is 0.30000000000000004 as floats
    totals = domain.CreditTotals.of(cents)
    assert totals.credits == Decimal("0.3")
    assert totals.model_dump(mode="json")["credits"] == 0.3

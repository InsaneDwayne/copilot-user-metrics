"""Hand-written read queries: the member list, team models, model tokens, sync jobs and org report use.

All values are bind parameters.
"""

from sqlalchemy import text

# A person's teams are those of the last day on or before :end that GitHub listed them on.
# The day is per person: the latest report day alone (often partial, or only listing people
# active that day) would drop everyone it doesn't mention, and with them whole teams.
# TEAM_MODELS_SQL uses the same rule.
MEMBERS_SQL = text("""
WITH credits AS (
    SELECT user_id, model, sum(gross_qty) AS credits, sum(gross_usd) AS gross_usd
    FROM credit_usage WHERE day BETWEEN :start AND :end
    GROUP BY user_id, model
), per_user AS (
    SELECT user_id, sum(credits) AS credits, sum(gross_usd) AS gross_usd,
           (array_agg(model ORDER BY credits DESC))[1] AS top_model
    FROM credits GROUP BY user_id
), latest_teams AS (
    SELECT t.user_id, array_agg(t.team_slug ORDER BY t.team_slug) AS teams
    FROM user_team_day t
    JOIN (SELECT user_id, max(day) AS day FROM user_team_day WHERE day <= :end GROUP BY user_id) last
        USING (user_id, day)
    GROUP BY t.user_id
), act AS (
    -- An active day is any prompt, generated code or surface used (domain.is_active_day).
    SELECT user_id, sum(generations) AS generations, sum(acceptances) AS acceptances, sum(prompts) AS prompts,
           count(*) FILTER (
               WHERE prompts > 0 OR generations > 0
                  OR used_chat OR used_agent OR used_cli OR used_cloud_agent OR used_app OR used_review
           ) AS active_days
    FROM user_activity WHERE day BETWEEN :start AND :end
    GROUP BY user_id
), phase AS (
    SELECT DISTINCT ON (user_id) user_id, raw->'ai_adoption_phase' AS adoption_phase
    FROM user_activity
    WHERE day BETWEEN :start AND :end AND jsonb_typeof(raw->'ai_adoption_phase') = 'object'
    ORDER BY user_id, day DESC
)
SELECT s.user_id, s.login, s.avatar_url, s.assigned_at, s.ended_at, s.last_activity_at, s.last_activity_editor,
       s.pending_cancellation_date,
       coalesce(t.teams, array_remove(ARRAY[s.assigning_team], NULL)) AS teams,
       coalesce(u.credits, 0) AS credits, coalesce(u.gross_usd, 0) AS gross_usd, u.top_model,
       coalesce(a.generations, 0) AS generations, coalesce(a.acceptances, 0) AS acceptances,
       coalesce(a.prompts, 0) AS prompts, coalesce(a.active_days, 0) AS active_days, p.adoption_phase
FROM seat s
LEFT JOIN per_user u USING (user_id)
LEFT JOIN latest_teams t USING (user_id)
LEFT JOIN act a USING (user_id)
LEFT JOIN phase p USING (user_id)
WHERE s.ended_at IS NULL OR s.ended_at::date >= :start
""")


TEAM_MODELS_SQL = text("""
SELECT t.team_slug AS team, c.model, sum(c.gross_qty) AS credits
FROM credit_usage c
JOIN user_team_day t ON t.user_id = c.user_id
JOIN (SELECT user_id, max(day) AS day FROM user_team_day WHERE day <= :end GROUP BY user_id) last
    ON last.user_id = t.user_id AND last.day = t.day
WHERE c.day BETWEEN :start AND :end
GROUP BY t.team_slug, c.model
""")

# Sums the raw metrics in place: totals_by_client[].totals_by_model[] per day, client and
# model, across people. Client and the custom-model flag stay so the domain can name the
# models GitHub reports as "unknown". Missing or non-array breakdowns (records from before GitHub
# added them) count as empty.
MODEL_TOKENS_SQL = text("""
SELECT a.day, c->>'client' AS client, m->>'model' AS model,
       coalesce(m->'is_custom_enterprise_model' = 'true'::jsonb, false) AS custom_model,
       coalesce(sum((m->>'request_count')::numeric), 0)::bigint AS requests,
       coalesce(sum((m->'token_usage'->>'prompt_tokens_sum')::numeric), 0)::bigint AS prompt_tokens,
       coalesce(sum((m->'token_usage'->>'output_tokens_sum')::numeric), 0)::bigint AS output_tokens
FROM user_activity a
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(a.raw->'totals_by_client') = 'array' THEN a.raw->'totals_by_client' ELSE '[]' END
) c
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(c->'totals_by_model') = 'array' THEN c->'totals_by_model' ELSE '[]' END
) m
WHERE a.day BETWEEN :start AND :end
  AND (CAST(:user_id AS bigint) IS NULL OR a.user_id = CAST(:user_id AS bigint))
GROUP BY 1, 2, 3, 4
""")

JOBS_SQL = text("""
SELECT DISTINCT ON (r.job)
       r.job, r.started_at AS last_started_at, r.status AS last_status, r.error AS last_error, r.rows AS last_rows,
       ok.finished_at AS last_success_at,
       (SELECT count(*) FROM sync_run f
         WHERE f.job = r.job AND f.status = :failed
           AND f.started_at > coalesce(ok.finished_at, '-infinity')) AS failures_since_success
FROM sync_run r
LEFT JOIN LATERAL (
    SELECT finished_at FROM sync_run s WHERE s.job = r.job AND s.status = :succeeded
    ORDER BY finished_at DESC LIMIT 1
) ok ON true
ORDER BY r.job, r.started_at DESC
""")


# Interactions per named entry of one breakdown in the raw org reports (MCP servers, custom
# agents). A missing or non-array breakdown counts as empty, as for the per-user ones.
REPORT_USE_SQL = text("""
SELECT e->>CAST(:name AS text) AS name,
       coalesce(sum((e->>'interaction_count')::numeric), 0)::bigint AS count
FROM org_activity_day a
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(a.raw->CAST(:key AS text)) = 'array' THEN a.raw->CAST(:key AS text) ELSE '[]' END
) e
WHERE a.day BETWEEN :start AND :end AND e->>CAST(:name AS text) IS NOT NULL
GROUP BY 1
""")

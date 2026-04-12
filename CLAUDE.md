# AI Cohost

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

## Database Migrations

After pulling new code, ALWAYS run:

    cd apps/api && uv run alembic upgrade head

The API server will warn (dev) or fail (production) if migrations are
out of sync — this is enforced by `app.core.migrations` in the FastAPI
lifespan hook. The test runner auto-applies migrations to the test DB.

If you see `UndefinedColumnError` in API or Celery logs, your dev DB is
behind code. Quick fix: `alembic upgrade head` then restart `api` and
`celery`. (This exact failure shape caused the 2026-04-12 silent
comment-pipeline outage — zero AI suggestions despite a healthy
worker, because the optimistic extension UI hid the DB error.)

## AI Insights — keep recommendations grounded in real UI

The session-insights LLM (`app.services.session_insights`) is constrained
to only recommend actions that exist in the dashboard. The contract is
in `app.services.insights.allowed_actions.ALLOWED_ACTIONS`. Skipping the
contract leads to hallucinated features ("Vào cài đặt AI > thêm intent
greeting") that erode user trust — this happened in production once
already, hence the guard.

**When you ADD a user-facing feature** that AI Insights might want to
recommend (a new product field, a new moderation toggle, a new script
tab, etc):

1. Add an entry to `allowed_actions.py` in the matching section.
2. Use the exact Vietnamese navigation path the user sees in the UI.
3. Set `plan_required` to the cheapest plan that unlocks the feature.
4. Update the `test_plan_counts_match_design` assertion in
   `tests/test_session_insights.py` if the per-tier counts shift.

**When you REMOVE a user-facing feature**:

1. Delete the entry from `allowed_actions.py`.
2. Add the now-stale label fragment to `FORBIDDEN_PHRASES` in
   `session_insights.py`. This stops cached prompts from sneaking it
   back via few-shot memory.
3. The Redis cache TTL is 10 minutes (`_CACHE_TTL_SECONDS = 600`), so
   stale recommendations automatically roll over within ten minutes
   after a deploy. No manual cache clear needed.

**Validation flow**: every LLM response runs through
`_validate_against_hallucination` and `_is_generic_insight`. If either
fires the loop retries with a targeted suffix (`_RETRY_SUFFIX_HALLUCINATION`
or `_RETRY_SUFFIX_GENERIC`). After the final attempt, offending items
are filtered from the payload and the user sees a `warning` field
explaining how many cards were hidden — better to show fewer cards
than to lie about the product surface.

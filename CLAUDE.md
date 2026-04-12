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

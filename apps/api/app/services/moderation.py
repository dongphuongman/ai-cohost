"""Moderation service — CRUD for shop rules and flagged comment management."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation import FlaggedComment, ShopModerationRules
from app.models.session import Comment
from app.services.comment_classifier import ShopRules


async def get_rules(db: AsyncSession, shop_id: int) -> ShopModerationRules | None:
    result = await db.execute(
        select(ShopModerationRules).where(ShopModerationRules.shop_id == shop_id)
    )
    return result.scalar_one_or_none()


async def get_shop_rules(db: AsyncSession, shop_id: int) -> ShopRules:
    """Load shop moderation rules as a ShopRules dataclass for the classifier."""
    row = await get_rules(db, shop_id)
    if not row:
        return ShopRules()
    return ShopRules(
        blocked_keywords=row.blocked_keywords or [],
        blocked_patterns=row.blocked_patterns or [],
        whitelisted_users=row.whitelisted_users or [],
        blacklisted_users=row.blacklisted_users or [],
        auto_hide_spam=row.auto_hide_spam,
        auto_hide_links=row.auto_hide_links,
        auto_flag_toxic=row.auto_flag_toxic,
        emoji_flood_threshold=row.emoji_flood_threshold,
        min_comment_length=row.min_comment_length,
        use_llm_classify=row.use_llm_classify,
        llm_classify_rate_limit=row.llm_classify_rate_limit,
    )


def _validate_patterns(patterns: list[str] | None) -> None:
    """Validate regex patterns at write time to prevent ReDoS."""
    if not patterns:
        return
    import re
    for p in patterns:
        if len(p) > 200:
            raise ValueError(f"Pattern quá dài (tối đa 200 ký tự): {p[:50]}...")
        try:
            re.compile(p)
        except re.error as e:
            raise ValueError(f"Regex không hợp lệ '{p}': {e}")


async def upsert_rules(db: AsyncSession, shop_id: int, **kwargs) -> ShopModerationRules:
    """Create or update moderation rules for a shop."""
    if "blocked_patterns" in kwargs and kwargs["blocked_patterns"] is not None:
        _validate_patterns(kwargs["blocked_patterns"])
    row = await get_rules(db, shop_id)
    if row:
        for key, value in kwargs.items():
            if value is not None:
                setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
    else:
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        row = ShopModerationRules(shop_id=shop_id, **filtered)
        db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def flag_comment(db: AsyncSession, comment_id: int, shop_id: int, reason: str | None = None) -> FlaggedComment:
    """Flag a comment for manual review."""
    flagged = FlaggedComment(
        comment_id=comment_id,
        shop_id=shop_id,
        reason=reason,
    )
    db.add(flagged)
    await db.flush()
    await db.refresh(flagged)
    return flagged


async def list_flagged(
    db: AsyncSession, shop_id: int, status: str = "pending", limit: int = 50, offset: int = 0
) -> list[dict]:
    """List flagged comments with comment text for a shop."""
    result = await db.execute(
        select(FlaggedComment, Comment.text_, Comment.external_user_name)
        .join(Comment, FlaggedComment.comment_id == Comment.id)
        .where(FlaggedComment.shop_id == shop_id, FlaggedComment.status == status)
        .order_by(FlaggedComment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()
    return [
        {
            "id": flagged.id,
            "comment_id": flagged.comment_id,
            "external_user_name": user_name,
            "text": text,
            "reason": flagged.reason,
            "status": flagged.status,
            "created_at": flagged.created_at.isoformat() if flagged.created_at else None,
        }
        for flagged, text, user_name in rows
    ]


async def review_flagged(
    db: AsyncSession, flagged_id: int, shop_id: int, action: str, user_id: int
) -> FlaggedComment | None:
    """Approve or dismiss a flagged comment."""
    result = await db.execute(
        select(FlaggedComment).where(
            FlaggedComment.id == flagged_id,
            FlaggedComment.shop_id == shop_id,
        )
    )
    flagged = result.scalar_one_or_none()
    if not flagged:
        return None

    flagged.status = action  # "approved" or "dismissed"
    flagged.reviewed_by = user_id
    flagged.reviewed_at = datetime.now(timezone.utc)

    # If dismissed, also mark the comment as spam
    if action == "dismissed":
        await db.execute(
            update(Comment)
            .where(Comment.id == flagged.comment_id)
            .values(is_spam=True)
        )

    # If approved, unflag the comment
    if action == "approved":
        await db.execute(
            update(Comment)
            .where(Comment.id == flagged.comment_id)
            .values(is_spam=False)
        )

    await db.flush()
    await db.refresh(flagged)
    return flagged


async def bulk_review(
    db: AsyncSession, shop_id: int, comment_ids: list[int], action: str, user_id: int
) -> int:
    """Bulk approve or dismiss flagged comments. Returns count of updated rows."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(FlaggedComment)
        .where(
            FlaggedComment.shop_id == shop_id,
            FlaggedComment.comment_id.in_(comment_ids),
            FlaggedComment.status == "pending",
        )
        .values(status=action, reviewed_by=user_id, reviewed_at=now)
    )

    if action == "dismissed":
        await db.execute(
            update(Comment)
            .where(Comment.id.in_(comment_ids))
            .values(is_spam=True)
        )
    elif action == "approved":
        await db.execute(
            update(Comment)
            .where(Comment.id.in_(comment_ids))
            .values(is_spam=False)
        )

    return result.rowcount

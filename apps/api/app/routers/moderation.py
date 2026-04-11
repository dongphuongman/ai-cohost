from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.moderation import (
    BulkActionRequest,
    ModerationRulesResponse,
    ModerationRulesUpdate,
)
from app.services import moderation as moderation_svc

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/rules", response_model=ModerationRulesResponse)
async def get_rules(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    row = await moderation_svc.get_rules(db, shop.shop_id)
    if not row:
        return ModerationRulesResponse()
    return ModerationRulesResponse(
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


@router.patch("/rules", response_model=ModerationRulesResponse)
async def update_rules(
    body: ModerationRulesUpdate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    row = await moderation_svc.upsert_rules(
        db, shop.shop_id, **body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ModerationRulesResponse(
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


@router.get("/flagged")
async def list_flagged(
    status_filter: str = "pending",
    limit: int = 50,
    offset: int = 0,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if status_filter not in ("pending", "approved", "dismissed"):
        raise HTTPException(status_code=400, detail="Status phải là pending, approved hoặc dismissed")
    return await moderation_svc.list_flagged(db, shop.shop_id, status=status_filter, limit=limit, offset=offset)


@router.post("/flagged/{flagged_id}/approve")
async def approve_flagged(
    flagged_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await moderation_svc.review_flagged(db, flagged_id, shop.shop_id, "approved", shop.user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy comment")
    await db.commit()
    return {"status": "approved"}


@router.post("/flagged/{flagged_id}/dismiss")
async def dismiss_flagged(
    flagged_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await moderation_svc.review_flagged(db, flagged_id, shop.shop_id, "dismissed", shop.user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy comment")
    await db.commit()
    return {"status": "dismissed"}


@router.post("/bulk")
async def bulk_action(
    body: BulkActionRequest,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if body.action not in ("approve", "dismiss"):
        raise HTTPException(status_code=400, detail="Action phải là approve hoặc dismiss")
    # Map to past tense for DB status
    db_action = "approved" if body.action == "approve" else "dismissed"
    count = await moderation_svc.bulk_review(db, shop.shop_id, body.comment_ids, db_action, shop.user_id)
    await db.commit()
    return {"updated": count}

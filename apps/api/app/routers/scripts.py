import asyncio
import html as html_mod
import io
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.scripts import (
    GenerateResponse,
    ScriptConfig,
    ScriptListResponse,
    ScriptResponse,
    ScriptUpdate,
)
from app.services import scripts as script_svc
from app.services.embed_client import get_job_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("/jobs/{job_id}/status")
async def check_job_status(
    job_id: str,
    shop: ShopContext = Depends(get_current_shop),
):
    result = await get_job_status(job_id)
    if result is None:
        return {"status": "pending"}
    return result


@router.get("/", response_model=ScriptListResponse)
async def list_scripts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: int | None = None,
    persona_id: int | None = None,
    tone: str | None = None,
    search: str | None = None,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    return await script_svc.list_scripts(
        db, shop.shop_id,
        page=page, page_size=page_size,
        product_id=product_id, persona_id=persona_id,
        tone=tone, search=search,
    )


@router.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate_script(
    config: ScriptConfig,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    try:
        job_id = await script_svc.start_generation(
            db, shop.shop_id, shop.user_id, config,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e),
        )
    return GenerateResponse(job_id=job_id)


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await script_svc.get_script(db, shop.shop_id, script_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script không tồn tại",
        )
    return result


@router.patch("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: int,
    data: ScriptUpdate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await script_svc.update_script(
        db, shop.shop_id, script_id, data.content,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script không tồn tại",
        )
    return result


@router.delete("/{script_id}", status_code=204)
async def delete_script(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if not await script_svc.delete_script(db, shop.shop_id, script_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script không tồn tại",
        )


@router.post("/{script_id}/regenerate", response_model=GenerateResponse, status_code=202)
async def regenerate_script(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    try:
        job_id, _version = await script_svc.start_regeneration(
            db, shop.shop_id, shop.user_id, script_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e),
        )
    return GenerateResponse(job_id=job_id)


@router.get("/{script_id}/export/md")
async def export_markdown(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    script = await script_svc.get_script(db, shop.shop_id, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script không tồn tại")

    md = f"# {script.title}\n\n{script.content}"
    filename = f"script-{script.id}.md"
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{script_id}/export/txt")
async def export_text(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    script = await script_svc.get_script(db, shop.shop_id, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script không tồn tại")

    # Strip markdown headings for plain text
    plain = re.sub(r"^#+\s*", "", script.content, flags=re.MULTILINE)
    plain = f"{script.title}\n{'=' * len(script.title)}\n\n{plain}"
    filename = f"script-{script.id}.txt"
    return Response(
        content=plain.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{script_id}/export/pdf")
async def export_pdf(
    script_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    script = await script_svc.get_script(db, shop.shop_id, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script không tồn tại")

    try:
        import markdown2
        from weasyprint import HTML
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export chưa sẵn sàng (thiếu weasyprint/markdown2)",
        )

    html_content = markdown2.markdown(
        script.content, extras=["fenced-code-blocks"],
    )
    duration_min = (script.estimated_duration_seconds or 0) // 60
    created = script.created_at.strftime("%d/%m/%Y %H:%M") if script.created_at else ""
    safe_title_html = html_mod.escape(script.title)

    styled_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: sans-serif; padding: 50px; color: #111827; line-height: 1.7; }}
h1 {{ color: #5B47E0; font-size: 24px; margin-bottom: 8px; }}
h2 {{ color: #2E75B6; font-size: 18px; margin-top: 24px; }}
.meta {{ color: #6B7280; font-size: 13px; margin-bottom: 20px; }}
.footer {{ color: #9CA3AF; font-size: 11px; text-align: center; margin-top: 40px; }}
</style></head><body>
<h1>{safe_title_html}</h1>
<div class="meta">AI Co-host &bull; {script.word_count or 0} tu &bull;
~{duration_min} phut &bull; {created}</div>
<hr>
{html_content}
<div class="footer">Tao boi AI Co-host</div>
</body></html>"""

    def _render_pdf():
        return HTML(string=styled_html, url_fetcher=lambda *a, **k: (_ for _ in ()).throw(ValueError("blocked"))).write_pdf()

    pdf_bytes = await asyncio.to_thread(_render_pdf)
    safe_title = re.sub(r'[^\w\s-]', '', script.title[:30]).strip()
    filename = f"script-{script.id}-{safe_title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

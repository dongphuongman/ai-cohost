from fastapi import APIRouter

router = APIRouter(prefix="/products/{product_id}/faqs", tags=["faqs"])


@router.get("/")
async def list_faqs(product_id: int):
    return []


@router.post("/")
async def create_faq(product_id: int):
    return {"message": "create faq endpoint"}


@router.patch("/{faq_id}")
async def update_faq(product_id: int, faq_id: int):
    return {"id": faq_id}


@router.delete("/{faq_id}")
async def delete_faq(product_id: int, faq_id: int):
    return {"message": "deleted"}

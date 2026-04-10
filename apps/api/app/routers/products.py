from fastapi import APIRouter

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/")
async def list_products():
    return []


@router.post("/")
async def create_product():
    return {"message": "create product endpoint"}


@router.get("/{product_id}")
async def get_product(product_id: int):
    return {"id": product_id}


@router.patch("/{product_id}")
async def update_product(product_id: int):
    return {"id": product_id}


@router.delete("/{product_id}")
async def delete_product(product_id: int):
    return {"message": "deleted"}

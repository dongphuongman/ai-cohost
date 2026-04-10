from fastapi import APIRouter

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("/")
async def list_scripts():
    return []


@router.post("/generate")
async def generate_script():
    return {"message": "script generation endpoint"}


@router.get("/{script_id}")
async def get_script(script_id: int):
    return {"id": script_id}


@router.patch("/{script_id}")
async def update_script(script_id: int):
    return {"id": script_id}


@router.delete("/{script_id}")
async def delete_script(script_id: int):
    return {"message": "deleted"}

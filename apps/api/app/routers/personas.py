from fastapi import APIRouter

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("/")
async def list_personas():
    return []


@router.post("/")
async def create_persona():
    return {"message": "create persona endpoint"}


@router.get("/{persona_id}")
async def get_persona(persona_id: int):
    return {"id": persona_id}


@router.patch("/{persona_id}")
async def update_persona(persona_id: int):
    return {"id": persona_id}


@router.delete("/{persona_id}")
async def delete_persona(persona_id: int):
    return {"message": "deleted"}

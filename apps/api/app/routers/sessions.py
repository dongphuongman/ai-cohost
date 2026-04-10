from fastapi import APIRouter

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/")
async def list_sessions():
    return []


@router.get("/{session_id}")
async def get_session(session_id: int):
    return {"id": session_id}


@router.get("/{session_id}/comments")
async def list_session_comments(session_id: int):
    return []


@router.get("/{session_id}/suggestions")
async def list_session_suggestions(session_id: int):
    return []

from fastapi import APIRouter
from app.state import state

router = APIRouter()


@router.get("/health")
async def health():
    # Quick DB connectivity check
    try:
        state.conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}

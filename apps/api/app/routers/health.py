from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/healthz",
    summary="Check API health",
    description="Return a lightweight liveness response without requiring authentication.",
)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

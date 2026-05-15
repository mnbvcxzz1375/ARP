from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User
from app.services.auth import create_api_key_for_user, get_or_create_user


router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    key_name: str = Field(default="default", min_length=1, max_length=256)


class RegisterResponse(BaseModel):
    user_id: str
    username: str
    api_key: str


@router.post("/register", response_model=RegisterResponse)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_session)
):
    user = await get_or_create_user(body.username, session)
    api_key = await create_api_key_for_user(user, body.key_name, session)
    await session.commit()
    return RegisterResponse(
        user_id=str(user.id),
        username=user.username,
        api_key=api_key,
    )
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentApprover, DbSession
from app.core.config import settings
from app.core.security import create_access_token
from app.services.accounts import authenticate_approver

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ApproverOut(BaseModel):
    username: str


@router.post("/login")
async def login(body: LoginIn, db: DbSession) -> TokenOut:
    approver = await authenticate_approver(db, body.username, body.password)
    if approver is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password.")
    return TokenOut(
        access_token=create_access_token(approver.username),
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/me")
async def me(approver: CurrentApprover) -> ApproverOut:
    return ApproverOut(username=approver.username)

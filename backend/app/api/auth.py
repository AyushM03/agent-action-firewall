from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentApprover, DbSession, Limiter
from app.core.config import settings
from app.core.security import create_access_token
from app.services.accounts import authenticate_approver
from app.services.login_guard import check_login_attempt

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
async def login(body: LoginIn, request: Request, db: DbSession, limiter: Limiter) -> TokenOut:
    throttle = await check_login_attempt(limiter, body.username, request.client.host if request.client else None)
    if throttle.unavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login is temporarily unavailable. Try again shortly.")
    if not throttle.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many login attempts. Try again in {throttle.retry_after_seconds}s.",
            headers={"Retry-After": str(throttle.retry_after_seconds)},
        )
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

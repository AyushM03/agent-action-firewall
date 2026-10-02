from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.actions import router as actions_router
from app.api.agents import router as agents_router
from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import settings
from app.core.db import engine
from app.core.safety import enforce_safe_configuration


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await enforce_safe_configuration(settings, engine)
    yield


app = FastAPI(title="Agent Action Firewall", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(actions_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(agents_router)

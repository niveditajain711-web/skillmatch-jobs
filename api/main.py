"""SkillMatch Jobs API entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_config
from api.routes import router
from api.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize config + Postgres before any request (loads .env / RAPIDAPI_KEY too)
    get_config()
    yield


app = FastAPI(
    title="SkillMatch Jobs API",
    description="Resume-aware job search with explainable match scores",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

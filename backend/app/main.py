"""FastAPI entrypoint: CORS, startup pre-warm, router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import kpis
from app.services import data_loader


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Spec D3: throwaway call to make the model VRAM-resident. Removes model
    # load time from the first real request. Does NOT cache any output.
    # TODO: call llm.prewarm() once app/llm/base.py exists.
    data_loader.load()  # parse JSON into DataFrames now, not on the first request
    yield


app = FastAPI(title="MFGX AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.llm_provider, "model": settings.llm_model}


app.include_router(kpis.router, prefix="/api")

# Remaining routers land here as each vertical slice is built.
# from app.routers import insights, root_cause, search
# app.include_router(insights.router, prefix="/api")
# app.include_router(root_cause.router, prefix="/api")
# app.include_router(search.router, prefix="/api")

"""FastAPI entrypoint: CORS, startup pre-warm, router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import kpis, insights, root_cause, search

from app.config import settings
from app.llm.base import get_client
from app.services.knowledge_base import get_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Spec D3: throwaway call to make the model VRAM-resident. Removes model
    # load time from the first real request. Does NOT cache any output.
    get_client().prewarm()
    # Build/open the Chroma index up front so the first search isn't slow.
    get_knowledge_base()
    # TODO: data_loader.load_all() - read JSON into DataFrames once, cache in module state.
    yield


app = FastAPI(title="MFGX AI Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(kpis.router)
app.include_router(insights.router)
app.include_router(root_cause.router)
app.include_router(search.router)

@app.get("/health")
def health():
    return {"status": "ok"}


# Routers land here as each vertical slice is built.
# from app.routers import kpis, insights, root_cause, search
# app.include_router(kpis.router, prefix="/api")
# app.include_router(insights.router, prefix="/api")
# app.include_router(root_cause.router, prefix="/api")
# app.include_router(search.router, prefix="/api")

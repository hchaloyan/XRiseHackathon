"""FastAPI entrypoint: CORS, startup pre-warm, router registration."""

from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import kpis, insights, root_cause, search

from app.config import settings
from app.llm.base import get_client
from app.services import data_loader
from app.services.knowledge_base import get_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Spec D3: throwaway call to make the model VRAM-resident. Removes model
    # load time from the first real request. Does NOT cache any output.
    data_loader.load()  # parse JSON into DataFrames now, not on the first request
    # Build/open the Chroma index up front so the first search isn't slow.
    get_knowledge_base()
    get_client().prewarm()

    # Generate the briefing in the background so it is already cached by the
    # time anyone opens the page. Off-thread on purpose: blocking startup on a
    # 12-15s generation delays every other endpoint too.
    Thread(target=insights.warm, daemon=True).start()
    yield


app = FastAPI(title="MFGX AI Backend", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers. Every router declares its routes without a prefix; the /api prefix
# is applied here, in one place.
app.include_router(kpis.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(root_cause.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}

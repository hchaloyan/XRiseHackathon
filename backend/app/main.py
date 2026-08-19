"""FastAPI entrypoint: CORS, startup pre-warm, router registration."""

import time
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# StaticFiles raises starlette's HTTPException, which fastapi's subclasses —
# catching the fastapi one here would silently never fire.
from starlette.exceptions import HTTPException
from app.routers import documents, kpis, insights, root_cause, search

from app.config import REPO_ROOT, settings
from app.llm.base import get_client
from app.services import data_loader
from app.services.knowledge_base import get_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # BLOCKING: only work the first paint genuinely needs. uvicorn binds the
    # port after lifespan returns, and run.py opens the window on that port, so
    # every second spent here is a second of blank screen.
    started = time.perf_counter()
    data_loader.load()  # parse JSON into DataFrames now, not on the first request
    # Build/open the Chroma index up front so the first search isn't slow.
    # Indexes the SOP corpus AND any uploads from previous sessions.
    get_knowledge_base()
    print(f"[startup] ready in {time.perf_counter() - started:.1f}s")

    # BACKGROUND: everything that needs the model. Prewarm used to sit above,
    # which meant the window waited on a cold 7B load - tens of seconds of
    # nothing before the first paint. It buys nothing there: the endpoints that
    # need the model are all cached or degrade gracefully.
    #
    # One thread, in order, on purpose. Three concurrent generations would
    # contend for the same model and finish later than three sequential ones.
    def _warm() -> None:
        # Throwaway call to make the model VRAM-resident. Removes
        # model load time from the first real request. Caches no output.
        get_client().prewarm()
        insights.warm()      # the briefing, visible on load
        root_cause.warm()    # the rows most likely to be clicked next

    Thread(target=_warm, daemon=True).start()
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
app.include_router(documents.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


class _SPA(StaticFiles):
    """Serve the built UI, falling back to index.html on a miss so BrowserRouter
    deep links (/metrics) survive a hard refresh. An unmatched /api path is left
    to 404 as JSON — handing the fetch wrapper an HTML page instead is a
    confusing way to find out an endpoint is missing.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # Test against the URL, not `path`: StaticFiles runs it through
            # os.path.normpath, so on Windows it arrives as "api\\nope".
            if exc.status_code != 404 or scope["path"].startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)


# Mounted last, so every route above wins over a same-named file. Absent when
# the UI hasn't been built — the vite dev server covers that case.
DIST = REPO_ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", _SPA(directory=DIST, html=True), name="ui")

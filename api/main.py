"""
FeedbackOS FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import ENV, FASTAPI_URL, validate_config
from api.routers import (
    analytics,
    calibration,
    dialogue,
    examples,
    reviews,
    rubrics,
    submissions,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = validate_config()
    if missing:
        logger.warning(
            "FeedbackOS starting with missing config keys: %s. "
            "Some features will not work until these are set.",
            ", ".join(missing),
        )
    else:
        logger.info("FeedbackOS API started successfully (env=%s).", ENV)
    yield


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FeedbackOS API",
    description="Rubric-based feedback standardization for 100xEngineers mid-capstone reviews.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Streamlit pages call FastAPI via server-side httpx (not browser fetch),
# so CORS is not enforced. Allow all origins to avoid deployment friction.
_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(submissions.router, prefix="/submissions", tags=["submissions"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
app.include_router(rubrics.router, prefix="/rubrics", tags=["rubrics"])
app.include_router(examples.router, prefix="/examples", tags=["examples"])
app.include_router(calibration.router, prefix="/calibration", tags=["calibration"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(dialogue.router, prefix="/dialogue", tags=["dialogue"])

# ---------------------------------------------------------------------------
# Root / health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health_check() -> dict:
    """Liveness check — returns 200 when the API is up."""
    return {"status": "ok", "env": ENV}



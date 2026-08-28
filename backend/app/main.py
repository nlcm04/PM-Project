from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assets, flow_alerts, holdings, picks, performance
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="HOSE Quant Portfolio & Screening Platform",
    description="Human-in-the-loop value/quality screening and portfolio tracking for HOSE equities.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(picks.router)
app.include_router(holdings.router)
app.include_router(performance.router)
app.include_router(assets.router)
app.include_router(flow_alerts.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

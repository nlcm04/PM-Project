from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetOut

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{ticker}", response_model=AssetOut)
def get_asset(ticker: str, db: Session = Depends(get_db)) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.ticker == ticker.upper()))
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker '{ticker}'")
    return asset

from typing import Dict
from sqlalchemy.sql.expression import text
from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session
from database.database import get_session
import logging

# Configure logging
logger = logging.getLogger(__name__)

health_check_router = APIRouter()

@health_check_router.get(
    "/",
    response_model=Dict[str, str],
    summary="Health check endpoint",
    description="Returns service health status")
async def health_check(session=Depends(get_session)) -> Dict[str, str]:
    """
    Health check endpoint for monitoring.

    Returns:
        Dict[str, str]: Health status message
    
    Raises:
        HTTPException: If service is unhealthy
    """
    try:
        session.execute(text('SELECT 1'))
        return {"status": "healthy", "database": "ok"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
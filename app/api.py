from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.health_check import health_check_router
from routes.users import users_router
from routes.balance import balance_router
from routes.auth import auth_router
from routes.predict import predict_router
from routes.admin import admin_router
from database.database import init_db
from database.config import get_settings
import uvicorn
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def create_application() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        FastAPI: Configured application instance
    """
    
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.API_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_check_router, prefix='api/health', tags=['Health'])
    app.include_router(users_router, prefix='/api/users', tags=['Users'])
    app.include_router(auth_router, prefix='/api/auth', tags=['Auth'])
    app.include_router(balance_router, prefix='/api/balance', tags=['Balance'])
    app.include_router(predict_router, prefix='/api/predict', tags=['Predict'])
    app.include_router(admin_router, prefix='/api/admin', tags=['Admin'])

    return app

app = create_application()

@app.on_event("startup") 
def on_startup():
    try:
        logger.info("Initializing database...")
        init_db(drop_all=True)
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Application shutting down...")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    uvicorn.run(
        'api:app',
        host='0.0.0.0',
        port=8080,
        reload=True,
        log_level="info"
    )
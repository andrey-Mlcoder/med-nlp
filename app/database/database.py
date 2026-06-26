from sqlmodel import SQLModel, Session, create_engine 
from .config import get_settings

def get_database_engine():
    """
    Create and configure the SQLAlchemy engine.
    
    Returns:
        Engine: Configured SQLAlchemy engine
    """
    settings = get_settings()
    
    engine = create_engine(
        url=settings.DATABASE_URL_psycopg,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    return engine

engine = get_database_engine()

def get_session():
    with Session(engine) as session:
        yield session
        
def init_db(drop_all: bool = False) -> None:
    
    try:
        engine = get_database_engine()
        if drop_all:
            SQLModel.metadata.drop_all(engine)
        
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            from services.crud.model import get_all_models
            models = get_all_models(session)
            if not models:
                from services.crud.model import create_model
                create_model(
                    name="Default Model",
                    model_type="ocr",
                    session=session)
                session.commit()
                print("Created default model")

            from services.crud.admin import create_test_admin
            create_test_admin(session)

            print("TEST ADMIN CREATED SUCCESSFULLY")

    
    except Exception as e:
        raise
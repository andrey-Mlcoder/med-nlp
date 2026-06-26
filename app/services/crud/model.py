from sqlmodel import Session, select
from typing import List, Optional
from models.model import ML_model

def get_all_models(session: Session) -> List[ML_model]:
    """Получить все ML модели"""
    statement = select(ML_model)
    return session.exec(statement).all()

def get_model_by_id(model_id: int, session: Session) -> Optional[ML_model]:
    """Получить модель по ID"""
    return session.get(ML_model, model_id)

def create_model(name: str, model_type: str = "ocr", languages: List[str] = None, session: Session = None) -> ML_model:
    """Создать новую ML модель"""
    model = ML_model(
        name=name,
        model_type=model_type)
    
    if languages:
        model.set_languages(languages)

    if session:
        session.add(model)
        session.commit()
        session.refresh(model)
    return model

def choose_model(session: Session) -> ML_model:
    """
    Возвращает первую доступную модель из базы данных.
    """
    first_model = session.query(ML_model).first()
    if not first_model:
        raise ValueError("Нет доступных моделей для обработки задачи.")
    return first_model

def get_model_stats(model_id: int, session: Session) -> Optional[dict]:
    """Получить статистику модели"""
    model = get_model_by_id(model_id, session)
    if not model:
        return None
    
    return model.get_stats()
from models.task import Task, TaskStatus
from models.user import User
from models.model import ML_model
from models.balance import Balance
from models.transaction import Transaction
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from typing import Optional
import logging
from fastapi import HTTPException, status
import uuid


logger = logging.getLogger(__name__)

def get_task_by_id(task_id: int, session: Session) -> Optional[Task]:
 
    try:
        statement = select(Task).where(Task.task_id == task_id).options(
            selectinload(User.tasks))
        task = session.exec(statement).first()
        return task
    except Exception as e:
        raise

def get_user_by_task_id(user_id: int, session: Session) -> Optional[User]:
 
    try:
        task = session.query(Task).filter(Task.user_id == user_id).first()
        if task:
            user = task.user
        return user
    except Exception as e:
        raise
        
def create_database_task(user_id: int, input_data: str, cost: float, description: Optional[str], session: Session) -> Optional[Task]:
    """
    Создает задачу для пользователя, проверяет баланс и готовит задачу для исполнения
    """
    from services.crud.balance import spend, refund

    
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise ValueError(f"Пользователь с ID {user_id} не найден")

    from services.crud.model import choose_model
    first_model = choose_model(session)
    if not first_model:
        raise ValueError("Нет доступных моделей для обработки задачи.")

    model_id = first_model.model_id
    model_name = first_model.name

    if user.balance.amount < cost:
        logger.error("Balance error")
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="There are not enough funds in your account. Please top up your balance")

    spend(user_id, cost, session)
    task_id = str(uuid.uuid4())

    task = Task(
        task_id=task_id,
        user_id=user_id,
        model_id=model_id,
        input_data=input_data,
        cost=cost,
        description=description or f"Задача для модели {model_name}",
        status=TaskStatus.PROCESSING
    )

    try:
        session.add(task)
        session.flush()
        session.commit()
        session.refresh(task)
        return task

    except Exception as e:
        session.rollback()
        raise ValueError(f"Ошибка при создании задачи: {str(e)}")
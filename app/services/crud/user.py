from models.user import User
from models.task import Task
from models.admin import Admin
from models.balance import Balance
from models.transaction import Transaction
from sqlmodel import Session, select, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict


def get_all_users(session: Session) -> List[User]:
  
    try:
        statement = select(User).options(
            selectinload(User.tasks).selectinload(Task.user)
        )
        users = session.exec(statement).all()
        return users
    except Exception as e:
        raise

def get_user_by_id(user_id: int, session: Session) -> Optional[User]:
  
    try:
        statement = select(User).where(User.user_id == user_id).options(
            selectinload(User.tasks)
        )
        user = session.exec(statement).first()
        return user
    except Exception as e:
        raise

def get_user_by_email(email: str, session: Session) -> Optional[User]:

    try:
        statement = select(User).where(User.email == email).options(
            selectinload(User.tasks)
        )
        user = session.exec(statement).first()
        return user
    except Exception as e:
        raise

def create_user(user: User, session: Session) -> User:
  
    try:
        balance = Balance(
            amount=0.0,
            user_id=None )
        user.balance = balance
        session.add(user)
        session.commit()
        session.refresh(user)

        if user.balance:
            user.balance.user_id = user.user_id
            session.commit()
            session.refresh(user)
            
        return user
    except Exception as e:
        session.rollback()
        raise

def delete_user(user_id: int, session: Session) -> bool:

    try:
        user = session.get(User, user_id)
        if not user:
            return False
            
        if user.balance:
            stmt = delete(Transaction).where(Transaction.balance_id == user.balance.balance_id)
            session.execute(stmt)
            session.delete(user.balance)

        stmt = delete(Task).where(Task.user_id == user_id)
        session.execute(stmt)
        
        session.delete(user)
        session.commit()
        return True

    except Exception as e:
        session.rollback()
        raise ValueError(f"Ошибка при удалении пользователя: {str(e)}")

def autorisation_user(email: str, password: str, session: Session) -> Optional[User]:

    user = get_user_by_email(email, session)
    if user and user.password == password:
        return user
    return None

def add_balance(user_id: int, amount: float, session: Session) -> Optional[Balance]:
    
    user = session.get(User, user_id)
    if user:
        from services.crud.admin import make_decision
        decision = make_decision({"amount": amount}, session)
        if decision["status"] == "approved":
           if user.balance:
               from services.crud.balance import deposit
               return deposit(user_id, amount, session)
    return None
            
def get_user_history(user_id: int, session: Session) -> Optional[Dict]:
   
    user = session.get(User, user_id)
    if user:
        statement = select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        tasks = session.exec(statement).all()
        history = []
        for task in tasks:
            event = {"task_id": task.task_id,
                    "description": task.description,
                    "cost": task.cost,
                    "created_at": task.created_at.isoformat()}
            history.append(event)
        return history
    return None
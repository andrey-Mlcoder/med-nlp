from models.balance import Balance
from models.user import User
from models.transaction import Transaction
from sqlmodel import Session, select
from typing import List, Optional

def get_balance_by_user_id(user_id: int, session: Session) -> Optional[Balance]:
    
    try:
        statement = select(Balance).where(Balance.user_id == user_id)
        balance = session.exec(statement).first()
        return balance
    except Exception as e:
        raise

def get_transactions_by_balance_id(balance_id: int, session: Session) -> List[Transaction]:
    
    transaction_history = session.query(Transaction).filter(Transaction.balance_id == balance_id).all()
    return transaction_history

def spend(user_id: int, amount: float, session: Session) -> Optional[Balance]:
   
    balance = get_balance_by_user_id(user_id, session)
    if balance and balance.amount >= amount:
        balance.amount -= amount
        transaction = Transaction(
                balance_id=balance.balance_id,
                amount=-amount)
        session.add(transaction)
        session.commit()
        return balance
    return None

def deposit(user_id: int, amount: float, session: Session) -> Optional[Balance]:
   
    balance = get_balance_by_user_id(user_id, session)
    if balance:
        balance.amount += amount
        transaction = Transaction(
                balance_id=balance.balance_id,
                amount=amount)
        session.add(transaction)
        session.commit()
        return balance
    return None

def refund(user_id: int, amount: float, session: Session) -> Optional[Balance]:

    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise ValueError(f"Пользователь с ID {user_id} не найден")

    balance.amount += amount
    transaction = Transaction(
        balance_id=balance.balance_id,
        amount=amount)
    session.add(transaction)
    session.commit()
    return balance
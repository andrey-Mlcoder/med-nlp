from models.balance import Balance
from models.transaction import Transaction
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from typing import Optional

def get_transaction_by_id(transaction_id: int, session: Session) -> Optional[Transaction]:
 
    try:
        statement = select(Transaction).where(Transaction.transaction_id == transaction_id).options(
            selectinload(Balance.transactions)
        )
        transaction = session.exec(statement).first()
        return transaction
    except Exception as e:
        raise
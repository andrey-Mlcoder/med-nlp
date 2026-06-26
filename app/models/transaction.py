from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.balance import Balance


class Transaction(SQLModel, table=True):
    
    "Класс транзакций"

    transaction_id: int = Field(default=None, primary_key=True)
    balance_id: int = Field(foreign_key='balance.balance_id')
    amount: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    balance: "Balance" = Relationship(back_populates="transactions")
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.transaction import Transaction


class Balance(SQLModel, table=True):
    __mapper_args__ = {"confirm_deleted_rows": False}

    "Класс баланс пользователя"
    balance_id: int = Field(default=None, primary_key=True)
    amount: float = Field(default=0.0)
    user_id: int = Field(foreign_key='user.user_id')
    transactions: List["Transaction"] = Relationship(back_populates="balance")
    user: "User" = Relationship(back_populates="balance")
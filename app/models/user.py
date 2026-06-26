from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.task import Task
    from models.balance import Balance


class User(SQLModel, table=True):

    "Класс Пользователя"

    user_id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(unique=True, index=True)
    password: str
    balance: Optional["Balance"] = Relationship(back_populates="user",  
                        sa_relationship_kwargs={
                        "cascade": "all, delete-orphan",
                        "lazy": "selectin",
                        "uselist": False})
    tasks: List["Task"] = Relationship(back_populates="user",
                        sa_relationship_kwargs={
                        "cascade": "all, delete-orphan",
                        "lazy": "selectin"})
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def get_info(self):
        #Просмотр информации о пользователе, в том числе о балансе
        balance_amount = self.balance.amount if self.balance else 0.0
        return {"user_id": self.user_id,
                "username": self.username,
                "email": self.email,
                "balance": balance_amount}
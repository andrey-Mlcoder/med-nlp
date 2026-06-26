from enum import Enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional, ClassVar, Dict
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
import uuid

if TYPE_CHECKING:
    from models.model import ML_model
    from models.user import User


class TaskStatus(Enum):

    "Класс для отображения статуса задачи"
    
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(SQLModel, table=True):
    __mapper_args__ = {"confirm_deleted_rows": False}
    "Задача для предсказания модели"

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()),
                                     primary_key=True)
    description: Optional[str] = None
    input_data: str
    output_data: Optional[str] = None
    cost: float = Field(default=10.0)
    user_id: int = Field(foreign_key="user.user_id")
    model_id: int = Field(foreign_key="ml_model.model_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="tasks")
    model: Optional["ML_model"] = Relationship(back_populates="tasks")
    status: TaskStatus = TaskStatus.PROCESSING
    
    valid_images: ClassVar[Dict[str, str]] = {'key1': 'value1', 'key2': 'value2'}

    def validate_input(self, input_data: str) -> bool:
        #Проверяем входные данные
        if input_data in self.valid_images.keys():
            return True
        return False


class TaskDTO(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_data: str
    status: TaskStatus = TaskStatus.PROCESSING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model: str= Field(default='EasyOcr')

    class Config:
        use_enum_values = True
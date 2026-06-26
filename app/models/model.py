from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
import json
from pydantic import ConfigDict

if TYPE_CHECKING:
    from models.task import Task


class ML_model(SQLModel, table=True):

    model_config = ConfigDict(protected_namespaces=())

    "ML модель для предсказаний"
    model_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="EasyOcr", index=True)
    version: str = Field(default="1.0.0")
    description: Optional[str] = None
    model_type: str = Field(default="ocr")
    languages: str = Field(default='["ru"]')
    tasks: List["Task"] = Relationship(back_populates="model")
    
    # Статистика использования
    total_predictions: int = Field(default=0)
    successful_predictions: int = Field(default=0)
    
    def get_languages(self) -> list:
        try:
            return json.loads(self.languages)
        except:
            return ["ru"]
    
    def set_languages(self, languages: list):
        
        self.languages = json.dumps(languages)
    
    def get_stats(self) -> dict:
        """Получить статистику модели"""
        success_rate = 0
        if self.total_predictions > 0:
            success_rate = (self.successful_predictions / self.total_predictions) * 100
        
        return {"id": self.model_id,
                "name": self.name,
                "version": self.version,
                "total_predictions": self.total_predictions,
                "successful_predictions": self.successful_predictions,
                "success_rate": round(success_rate, 2),}
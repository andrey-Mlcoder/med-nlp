from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional
import json

class Admin(SQLModel, table=True):
    
    "Класс Администратор"

    admin_id: int = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    history: Optional[str] = Field(default="{}")

    def get_history(self) -> dict:
        if self.history:
            try:
                return json.loads(self.history)
            except:
                return {}
        return {}
    
    def add_to_history(self, user_id: int, amount: float, description: str = ""):
        history_dict = self.get_history()
        
        user_key = str(user_id)
        if user_key not in history_dict:
            history_dict[user_key] = []
        
        history_dict[user_key].append({
            "amount": amount,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
        self.history = json.dumps(history_dict, default=str)
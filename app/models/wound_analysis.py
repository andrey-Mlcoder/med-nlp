from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.wound_image import WoundImage
    from models.alert import Alert

class WoundAnalysis(SQLModel, table=True):
    "Класс для анализа ран"
    __tablename__ = "wound_analyses"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    wound_image_id: int = Field(foreign_key="wound_images.id", nullable=False, index=True)
    
    # ML Model results
    dice_score: Optional[float] = Field(default=None)
    model_version: Optional[str] = Field(default=None)
    processing_time_ms: Optional[int] = Field(default=None)
    mask_path: Optional[str] = Field(default=None)
    
    # Clinical assessment
    doctor_id: Optional[int] = Field(default=None, foreign_key="users.id")
    doctor_notes: Optional[str] = Field(default=None)
    is_reviewed: bool = Field(default=False)
    reviewed_at: Optional[datetime] = Field(default=None)
    
    # Recommendations
    recommendation: Optional[str] = Field(default=None)
    follow_up_days: Optional[int] = Field(default=None)
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    
    # Relationships
    wound_image: Optional["WoundImage"] = Relationship(back_populates="analyses")
    doctor: Optional["User"] = Relationship()
    alerts: List["Alert"] = Relationship(back_populates="analysis") 
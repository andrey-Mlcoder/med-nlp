from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from models.wound_image import WoundImage
    from models.user import User
    from models.wound_analysis import WoundAnalysis

class AlertStatus(str, PyEnum):
    NEW = "new"
    VIEWED = "viewed"
    RESOLVED = "resolved"


class AlertSeverity(str, PyEnum):
    LOW = "low"           # незначительное увеличение
    MEDIUM = "medium"     # рост >15%
    CRITICAL = "critical" # рост >30% или подозрение на инфекцию


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    wound_image_id: int = Field(foreign_key="wound_images.id", nullable=False, index=True)
    doctor_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    patient_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    analysis_id: Optional[int] = Field(default=None, foreign_key="wound_analyses.id", index=True) 
    
    # Серьёзность
    severity: AlertSeverity = Field(
        sa_column=Column(SAEnum(AlertSeverity), nullable=False)
    )
    
    # Детали
    message: str = Field(nullable=False)  # текст уведомления
    area_change_pct: Optional[float] = Field(default=None)  # например, +23.5%
    
    # Статус
    status: AlertStatus = Field(
        default=AlertStatus.NEW,
        sa_column=Column(SAEnum(AlertStatus), nullable=False)
    )
    
    # Временные метки
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    viewed_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    
    # Relationships
    wound_image: Optional["WoundImage"] = Relationship()
    doctor: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Alert.doctor_id]"})
    patient: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Alert.patient_id]"})
    analysis: Optional["WoundAnalysis"] = Relationship(back_populates="alerts")
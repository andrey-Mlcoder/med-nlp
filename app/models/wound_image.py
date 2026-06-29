from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.wound_analysis import WoundAnalysis

class WoundImage(SQLModel, table=True):
    "Класс фото"
    __tablename__ = "wound_images"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    patient_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    
    # Image data
    image_path: str = Field(nullable=False)
    original_filename: str = Field(nullable=False)
    
    # Analysis results
    wound_area_pixels: Optional[int] = Field(default=None)
    wound_area_percentage: Optional[float] = Field(default=None)
    wound_area_cm2: Optional[float] = Field(default=None)
    
    # Metadata
    upload_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    notes: Optional[str] = Field(default=None)
    uploaded_by_doctor_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Comparison with previous
    previous_image_id: Optional[int] = Field(
        default=None, 
        foreign_key="wound_images.id"
    )
    area_change_percentage: Optional[float] = Field(default=None)
    is_alert: bool = Field(default=False)

    
    # Relationships
    patient: Optional["User"] = Relationship(
    back_populates="wound_images",
    sa_relationship_kwargs={"foreign_keys": "[WoundImage.patient_id]"}
)
    uploaded_by_doctor: Optional["User"] = Relationship(
    sa_relationship_kwargs={"foreign_keys": "[WoundImage.uploaded_by_doctor_id]"}
)
    previous_image: Optional["WoundImage"] = Relationship(
        sa_relationship_kwargs={"remote_side": "[WoundImage.id]"}
    )
    analyses: List["WoundAnalysis"] = Relationship(back_populates="wound_image")
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User


class PatientDoctorAssignment(SQLModel, table=True):
    __tablename__ = "patient_doctor_assignments"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    patient_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    doctor_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    
    assigned_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    is_active: bool = Field(default=True)
    
    # Relationships
    patient: Optional["User"] = Relationship(
        back_populates="assigned_as_patient",
        sa_relationship_kwargs={"foreign_keys": "[PatientDoctorAssignment.patient_id]"}
    )
    doctor: Optional["User"] = Relationship(
        back_populates="assigned_as_doctor",
        sa_relationship_kwargs={"foreign_keys": "[PatientDoctorAssignment.doctor_id]"}
    )
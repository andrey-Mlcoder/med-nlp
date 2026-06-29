from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from models.wound_image import WoundImage
    from models.patient_doctor import PatientDoctorAssignment
    from models.audit_log import AuditLog


class UserRole(PyEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class User(SQLModel, table=True):
    "Класс Пользователя"
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    full_name: str = Field(nullable=False)
    role: UserRole = Field(sa_column=Column(Enum(UserRole), nullable=False))
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    
    # Patient-specific
    phone: Optional[str] = Field(default=None)
    date_of_birth: Optional[datetime] = Field(default=None)
    
    # Doctor-specific
    specialization: Optional[str] = Field(default=None)
    medical_license: Optional[str] = Field(default=None)
    
    # Relationships
    wound_images: List["WoundImage"] = Relationship(
    back_populates="patient",
    sa_relationship_kwargs={"foreign_keys": "[WoundImage.patient_id]"}
)
    assigned_as_doctor: List["PatientDoctorAssignment"] = Relationship(
        back_populates="doctor",
        sa_relationship_kwargs={"foreign_keys": "[PatientDoctorAssignment.doctor_id]"}
    )
    assigned_as_patient: List["PatientDoctorAssignment"] = Relationship(
        back_populates="patient",
        sa_relationship_kwargs={"foreign_keys": "[PatientDoctorAssignment.patient_id]"}
    )
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from models.user import User

class ActionType(str, PyEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    UPLOAD_IMAGE = "upload_image"
    VIEW_IMAGE = "view_image"
    UPDATE_ANALYSIS = "update_analysis"
    RESOLVE_ALERT = "resolve_alert"
    ASSIGN_DOCTOR = "assign_doctor"
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    DELETE_IMAGE = "delete_image"
    ADMIN_ACTION = "admin_action"

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    action_type: ActionType = Field(
        sa_column=Column(SAEnum(ActionType), nullable=False)
    )
    target_id: Optional[str] = Field(default=None)   
    details: Optional[str] = Field(default=None)   
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    
    user: Optional["User"] = Relationship(back_populates="audit_logs")
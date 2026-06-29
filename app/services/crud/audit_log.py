from sqlmodel import Session, select
from datetime import datetime
from typing import Optional, List
from models.audit_log import AuditLog, ActionType
from models.user import User, UserRole
import json
from datetime import datetime


def log_action(session: Session, action: ActionType, user_id: Optional[int] = None,
               target_id: Optional[str] = None, details: Optional[dict] = None,
               ip_address: Optional[str] = None, user_agent: Optional[str] = None
              ) -> AuditLog:
    action_str = action.value if isinstance(action, ActionType) else action
    log = AuditLog(
        user_id=user_id,
        action_type=action,
        target_id=target_id,
        details=json.dumps(details, default=str) if details else None,
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def get_audit_logs(session: Session, current_user: User, limit: int = 100,
                   offset: int = 0, action_type: Optional[ActionType] = None,
                   user_id: Optional[int] = None) -> List[AuditLog]:
    """Только администратор может просматривать логи."""
    if current_user.role != UserRole.ADMIN:
        raise ValueError("Admin access required")
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    query = query.offset(offset).limit(limit)
    return session.exec(query).all()
    
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from database.database import get_session
from models.user import User, UserRole
from models.alert import Alert, AlertStatus
from models.audit_log import AuditLog
from models.patient_doctor import PatientDoctorAssignment
from services.crud.patient_doctor import assign_doctor, deactivate_assignment
from services.crud.alert import get_alerts, update_alert_status
from services.crud.user import get_user_by_email
from auth.authenticate import authenticate
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

admin_router = APIRouter()


def get_current_user(token: str = Depends(authenticate), session: Session = Depends(get_session)) -> User:
    user = get_user_by_email(token, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@admin_router.get('/users')
def get_all_users(admin: User = Depends(get_current_admin),
                        session: Session = Depends(get_session)
                       ) -> List:
    users = session.exec(select(User)).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at
        }
        for u in users
    ]


@admin_router.post('/assign-doctor')
def assign_doctor_to_patient(
    patient_id: int,
    doctor_id: int,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
) -> Dict:
    assignment = assign_doctor(patient_id, doctor_id, session, admin)
    return {"message": "Doctor assigned", "assignment_id": assignment.id}


@admin_router.get('/alerts')
def list_alerts(
    status: AlertStatus = None,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
) -> List:
    alerts = get_alerts(session, admin, status)  # admin видит все
    return alerts


@admin_router.patch('/alerts/{alert_id}/resolve')
def resolve_alert(
    alert_id: int,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
) -> Dict[str,str]:
    alert = update_alert_status(alert_id, AlertStatus.RESOLVED, session, admin)
    return {"message": "Alert resolved"}


@admin_router.get('/audit-logs')
def get_audit_logs(
    limit: int = Query(100, le=1000),
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
) -> List:
    logs = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return logs
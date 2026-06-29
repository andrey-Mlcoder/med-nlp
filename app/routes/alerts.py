from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database.database import get_session
from models.user import User
from models.alert import Alert, AlertStatus
from services.crud.alert import get_alerts, update_alert_status
from services.crud.user import get_user_by_email
from auth.authenticate import authenticate
from pydantic import BaseModel


alerts_router = APIRouter()


class AlertStatusUpdate(BaseModel):
    new_status: AlertStatus
    

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


@alerts_router.get('/')
def list_alerts(
    status: AlertStatus = None,
    severity: str = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    from models.alert import AlertSeverity
    severity_enum = AlertSeverity(severity) if severity else None
    alerts = get_alerts(session, current_user, status, severity_enum)
    return [
        {
            "id": a.id,
            "patient_id": a.patient_id,
            "message": a.message,
            "severity": a.severity.value,
            "status": a.status.value,
            "created_at": a.created_at.isoformat()
        }
        for a in alerts
    ]

@alerts_router.patch('/{alert_id}/status')
def change_alert_status(
    alert_id: int,
    update: AlertStatusUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    alert = update_alert_status(alert_id, update.new_status, session, current_user)
    return {"message": "Status updated"}
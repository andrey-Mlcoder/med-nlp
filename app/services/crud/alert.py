from sqlmodel import Session, select
from typing import Optional, List
from models.alert import Alert, AlertStatus, AlertSeverity
from models.user import User, UserRole
from models.patient_doctor import PatientDoctorAssignment
from models.audit_log import ActionType 
from services.crud.audit_log import log_action
import json
from datetime import datetime


def create_alert(wound_image_id: int, doctor_id: int, patient_id: int,
                 severity: AlertSeverity, message: str,
                 area_change_pct: Optional[float],
                 analysis_id: Optional[int],
                 session: Session
                ) -> Alert:
    """Создаётся воркером, без проверки прав."""
    try:
        alert = Alert(wound_image_id=wound_image_id,
                      doctor_id=doctor_id,
                      patient_id=patient_id,
                      severity=severity,
                      message=message,
                      area_change_pct=area_change_pct,
                      analysis_id=analysis_id,
                      status=AlertStatus.NEW
                     )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert
    except Exception as e:
        raise


def get_alerts(session: Session, current_user: User, status: Optional[AlertStatus] = None,
               severity: Optional[AlertSeverity] = None) -> List[Alert]:
    """Получение алертов с фильтрацией по роли."""
    try:
        query = select(Alert)
        if current_user.role == UserRole.PATIENT:
            query = query.where(Alert.patient_id == current_user.id)
        elif current_user.role == UserRole.DOCTOR:
            query = query.where(Alert.doctor_id == current_user.id)
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
        query = query.order_by(Alert.created_at.desc())
        return session.exec(query).all()
    except Exception as e:
        raise


def get_alert(alert_id: int, session: Session, current_user: User) -> Optional[Alert]:
    try:
        alert = session.get(Alert, alert_id)
        if not alert:
            return None
        if current_user.role == UserRole.ADMIN:
            return alert
        if current_user.role == UserRole.PATIENT and current_user.id == alert.patient_id:
            return alert
        if current_user.role == UserRole.DOCTOR and current_user.id == alert.doctor_id:
            return alert
        raise ValueError("Access denied")
    except Exception as e:
        raise


def update_alert_status(alert_id: int, new_status: AlertStatus, session: Session,
                        current_user: User) -> Optional[Alert]:
    try:
        alert = get_alert(alert_id, session, current_user)
        if not alert:
            raise ValueError("Alert not found")
        # Только врач или админ могут менять статус
        if current_user.role not in (UserRole.DOCTOR, UserRole.ADMIN):
            raise ValueError("Only doctor or admin can update alert")
        # Врач может менять только свои алерты
        alert.status = new_status
        if new_status == AlertStatus.VIEWED:
            alert.viewed_at = datetime.utcnow()
        elif new_status == AlertStatus.RESOLVED:
            alert.resolved_at = datetime.utcnow()
        session.add(alert)
        session.commit()
        session.refresh(alert)
        log_action(session, ActionType.RESOLVE_ALERT, current_user.id, target_id=str(alert_id), details={"new_status": new_status.value})
        return alert
    except Exception as e:
        raise
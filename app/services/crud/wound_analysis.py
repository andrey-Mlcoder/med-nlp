from sqlmodel import Session, select
from typing import Optional, List
from models.wound_analysis import WoundAnalysis
from models.user import User, UserRole
from models.wound_image import WoundImage
from models.audit_log import ActionType 
from services.crud.wound_image import get_wound_image
from services.crud.audit_log import log_action
import json
from datetime import datetime


def create_analysis(wound_image_id: int, dice_score: float, model_version: str,
                    mask_path: str, processing_time_ms: int, session: Session
                   ) -> WoundAnalysis:
    """Создаётся воркером, без проверки прав (системный вызов)."""
    try:
        analysis = WoundAnalysis(
            wound_image_id=wound_image_id,
            dice_score=dice_score,
            model_version=model_version,
            mask_path=mask_path,
            processing_time_ms=processing_time_ms
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        return analysis
    except Exception as e:
        raise


def get_analysis(analysis_id: int, session: Session, current_user: User) -> Optional[WoundAnalysis]:
    try:
        analysis = session.get(WoundAnalysis, analysis_id)
        if not analysis:
            return None
        image = get_wound_image(analysis.wound_image_id, session, current_user)
        if not image:
            return []
        return analysis
    except Exception as e:
        raise


def get_analyses_by_image(image_id: int, session: Session, current_user: User) -> List[WoundAnalysis]:
    try:
        image = get_wound_image(image_id, session, current_user)
        if not image:
            return []
        statement = select(WoundAnalysis).where(WoundAnalysis.wound_image_id == image_id).order_by(WoundAnalysis.created_at.desc())
        return session.exec(statement).all()
    except Exception as e:
        raise


def update_analysis(analysis_id: int, update_data: dict, session: Session, current_user: User) -> Optional[WoundAnalysis]:
    try:
        analysis = get_analysis(analysis_id, session, current_user)
        if not analysis:
            raise ValueError("Analysis not found")
        # Только врач или админ могут изменять анализ (добавлять заметки, рекомендации)
        if current_user.role not in (UserRole.DOCTOR, UserRole.ADMIN):
            raise ValueError("Only doctor or admin can update analysis")
        # Проверяем, что врач привязан к пациенту (если не админ)
        if current_user.role == UserRole.DOCTOR:
            image = session.get(WoundImage, analysis.wound_image_id)
            if image:
                assignment = session.exec(
                    select(PatientDoctorAssignment)
                    .where(PatientDoctorAssignment.patient_id == image.patient_id)
                    .where(PatientDoctorAssignment.doctor_id == current_user.id)
                    .where(PatientDoctorAssignment.is_active == True)
                ).first()
                if not assignment:
                    raise ValueError("You are not the assigned doctor for this patient")
        # Разрешённые поля
        allowed_fields = {"doctor_notes", "is_reviewed", "recommendation", "follow_up_days"}
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(analysis, key, value)
        if "is_reviewed" in update_data and update_data["is_reviewed"]:
            analysis.reviewed_at = datetime.utcnow()
            analysis.doctor_id = current_user.id
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        log_action(session, ActionType.UPDATE_ANALYSIS, current_user.id, target_id=str(analysis_id), details=update_data)
        return analysis
    except Exception as e:
        raise
        
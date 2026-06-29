from sqlmodel import Session, select
from typing import Optional, List
from models.wound_image import WoundImage
from models.user import User, UserRole
from models.patient_doctor import PatientDoctorAssignment
from models.audit_log import ActionType
from services.crud.audit_log import log_action
from services.crud.user import get_user_by_id


def create_wound_image(patient_id: int, image_path: str, original_filename: str,
                       session: Session, current_user: User, notes: Optional[str] = None
                       ) -> WoundImage:
    """Загрузка нового изображения. Пациент – только себе, врач – своим пациентам, админ – любому."""
    try:
        # Проверяем, что пациент существует
        patient = get_user_by_id(patient_id, session, current_user)
        if not patient:
            raise ValueError("Patient not found")
        # Проверяем, что current_user имеет право загружать для этого пациента
        if current_user.role == UserRole.PATIENT and current_user.id != patient_id:
            raise ValueError("You can only upload for yourself")
        if current_user.role == UserRole.DOCTOR:
            # Проверяем, что пациент привязан к этому врачу
            assignment = session.exec(
                select(PatientDoctorAssignment)
                .where(PatientDoctorAssignment.patient_id == patient_id)
                .where(PatientDoctorAssignment.doctor_id == current_user.id)
                .where(PatientDoctorAssignment.is_active == True)
            ).first()
            if not assignment:
                raise ValueError("This patient is not assigned to you")
        # Создаём запись
        image = WoundImage(
            patient_id=patient_id,
            image_path=image_path,
            original_filename=original_filename,
            notes=notes,
            uploaded_by_doctor_id=current_user.id if current_user.role == UserRole.DOCTOR else None
        )
        session.add(image)
        session.commit()
        session.refresh(image)
        log_action(session, ActionType.UPLOAD_IMAGE, user_id=current_user.id, target_id=str(image.id))
        return image
    except Exception as e:
        raise
    

def get_wound_image(image_id: int, session: Session, current_user: Optional[User] = None,
                    skip_permission_check: bool = False) -> Optional[WoundImage]:
    image = session.get(WoundImage, image_id)
    if not image:
        return None
    if skip_permission_check:
        return image
    if current_user is None:
        raise ValueError("User required for permission check")
    if current_user.role == UserRole.ADMIN:
        return image
    if current_user.role == UserRole.PATIENT and current_user.id == image.patient_id:
        return image
    if current_user.role == UserRole.DOCTOR:
        assignment = session.exec(
            select(PatientDoctorAssignment)
            .where(PatientDoctorAssignment.patient_id == image.patient_id)
            .where(PatientDoctorAssignment.doctor_id == current_user.id)
            .where(PatientDoctorAssignment.is_active == True)
        ).first()
        if assignment:
            return image
    raise ValueError("Access denied")
    

def get_patient_images(patient_id: int, session: Session, current_user: User) -> List:
    """Получить все изображения пациента с проверкой прав."""
    try:
        user = get_user_by_id(patient_id, session, current_user)
        if not user:
             []
        statement = select(WoundImage).where(WoundImage.patient_id == patient_id).order_by(WoundImage.upload_date.desc())
        return session.exec(statement).all()
    except Exception as e:
        raise

    
def update_wound_image(image_id: int, update_data: dict, session: Session, 
                       current_user: Optional[User] = None, 
                       skip_permission_check: bool = False) -> Optional[WoundImage]:
    try:
        image = get_wound_image(image_id, session, current_user, skip_permission_check)
        if not image:
            raise ValueError("Image not found")
        allowed_fields = {
            "notes", "wound_area_pixels", "wound_area_percentage", 
            "area_change_percentage", "previous_image_id", "is_alert"
        }
        for key, value in update_data.items():
            if key in allowed_fields and hasattr(image, key):
                setattr(image, key, value)
        session.add(image)
        session.commit()
        session.refresh(image)
        # Логируем только если есть current_user (не системный вызов)
        if current_user and not skip_permission_check:
            log_action(session, ActionType.UPDATE_ANALYSIS, current_user.id, target_id=str(image_id), details={"updated": list(update_data.keys())})
        return image
    except Exception as e:
        session.rollback()
        raise
        

def delete_wound_image(image_id: int, session: Session, current_user: User) -> bool:
    """Удаление изображения. Только владелец-пациент или администратор."""
    try:
        image = session.get(WoundImage, image_id)
        if not image:
            return False
        if current_user.role == UserRole.ADMIN:
            pass
        elif current_user.role == UserRole.PATIENT and current_user.id == image.patient_id:
            pass
        else:
            raise ValueError("Only patient or admin can delete")
        session.delete(image)
        session.commit()
        log_action(session, ActionType.DELETE_IMAGE, current_user.id, target_id=str(image_id), details={"type": "wound_image"})
        return True
    except Exception as e:
        raise
    
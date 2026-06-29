from sqlmodel import Session, select, delete
from sqlalchemy.orm import selectinload
from models.user import User, UserRole
from models.patient_doctor import PatientDoctorAssignment
from models.audit_log import AuditLog, ActionType
from services.crud.audit_log import log_action
from typing import List, Optional, Dict, Any
from auth.hash_password import HashPassword
import logging

logger = logging.getLogger(__name__)


def get_all_users(session: Session, current_user: User) -> List[User]:
    try:
        if current_user.role != UserRole.ADMIN:
            raise ValueError("Admin access required")     
        statement = select(User).options(selectinload(User.wound_images))
        return session.exec(statement).all()
    except Exception as e:
        raise


def get_user_by_id(user_id: int, session: Session, current_user: User) -> Optional[User]:
    """Проверяет доступ: пациент – только себя, врач – своих пациентов, админ – любого."""
    try:
        user = session.get(User, user_id)
        if not user:
            return None
        if current_user.role == UserRole.ADMIN:
            return user
        if current_user.role == UserRole.PATIENT and current_user.id == user_id:
            return user
        if current_user.role == UserRole.DOCTOR:
            # Проверяем, что этот пациент привязан к врачу
            assignment = session.exec(
                select(PatientDoctorAssignment)
                    .where(PatientDoctorAssignment.patient_id == user_id)
                    .where(PatientDoctorAssignment.doctor_id == current_user.id)
                    .where(PatientDoctorAssignment.is_active == True)
            ).first()
        if assignment:
            return user
    except Exception as e:
        raise


def get_user_by_email(email: str, session: Session) -> Optional[User]:
    try:
        statement = select(User).where(User.email == email)
        return session.exec(statement).first()
    except Exception as e:
        raise

    
def create_patient(user_data: Dict[str, Any], session: Session) -> User:
    """Создаёт нового пациента."""
    try:
        # Проверяем, что email не занят
        existing = get_user_by_email(user_data["email"], session)
        if existing:
            raise ValueError("Email already registered")
        # Хешируем пароль
        hashed = HashPassword().create_hash(user_data["password"])
        # Создаём объект User
        user = User(
            email=user_data["email"],
            hashed_password=hashed,
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            date_of_birth=user_data.get("date_of_birth"),
            role=UserRole.PATIENT,
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        log_action(session, ActionType.CREATE_USER, user.id, target_id=str(user.id), details={"role": "patient"})
        return user
    except Exception as e:
        session.rollback()
        raise

def create_doctor(admin_user: User, user_data: Dict[str, Any], session: Session) -> User:
    """
    Создаёт нового врача. Доступно только администратору.
    admin_user – текущий авторизованный администратор.
    """
    try:
        if admin_user.role != UserRole.ADMIN:
            raise ValueError("Admin access required")     
        # Проверяем email
        existing = get_user_by_email(user_data["email"], session)
        if existing:
            raise ValueError("Email already registered")
        # Хешируем пароль
        hashed = HashPassword().create_hash(user_data["password"])   
        # Создаём объект User с ролью DOCTOR
        user = User(
            email=user_data["email"],
            hashed_password=hashed,
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            specialization=user_data.get("specialization"),
            medical_license=user_data.get("medical_license"),
            role=UserRole.DOCTOR,
            is_active=True
        )       
        session.add(user)
        session.commit()
        session.refresh(user)
        log_action(session, ActionType.CREATE_USER, admin_user.id, target_id=str(user.id), details={"role": "doctor"})      
        return user
    except Exception as e:
        session.rollback()
        raise


def update_user(user_id: int, update_data: dict, session: Session, current_user: User) -> Optional[User]:
    """Обновление данных пользователя."""
    try:
        user = get_user_by_id(user_id, session, current_user)
        if not user:
            raise ValueError("User not found")
        # Обновляем только разрешённые поля
        allowed_fields = {"full_name", "phone", "date_of_birth", "specialization", "medical_license"}
        for key, value in update_data.items():
            if key in allowed_fields and hasattr(user, key):
                setattr(user, key, value)
        session.add(user)
        session.commit()
        session.refresh(user)
        log_action(session, ActionType.UPDATE_USER, current_user.id, target_id=str(user_id), details={"updated_fields": list(update_data.keys())})
        return user
    except Exception as e:
        raise
        

def delete_user(user_id: int, session: Session, current_user: User) -> bool:
    """Пациент может удалить только себя, администратор – любого."""
    try:
        if current_user.role == UserRole.PATIENT and current_user.id != user_id:
            raise ValueError("You can only delete your own account!")
        if current_user.role == UserRole.DOCTOR:
            raise ValueError("Doctors cannot delete users")
        user = session.get(User, user_id)
        if not user:
            return False
        session.delete(user)
        session.commit()
        log_action(session, ActionType.DELETE_USER, current_user.id, target_id=str(user_id))
        return True
    except Exception as e:
        raise


def get_my_patients(session: Session, current_user: User) -> List[User]:
    """Для врача – список активных пациентов."""
    try:
        if current_user.role != UserRole.DOCTOR:
            raise ValueError("Only doctors can view patients")
        assignments = session.exec(
            select(PatientDoctorAssignment)
            .where(PatientDoctorAssignment.doctor_id == current_user.id)
            .where(PatientDoctorAssignment.is_active == True)
        ).all()
        patient_ids = [assignment.patient_id for assignment in assignments]
        if not patient_ids:
            return []
        users = session.exec(select(User).where(User.id.in_(patient_ids))).all()
        return users
    except Exception as e:
        raise
        

def get_my_doctor(session: Session, current_user: User) -> Optional[User]:
    """Для пациента – его активный врач."""
    try:
        if current_user.role != UserRole.PATIENT:
            raise ValueError("Only patients can view their doctor")
        assignment = session.exec(
            select(PatientDoctorAssignment)
            .where(PatientDoctorAssignment.patient_id == current_user.id)
            .where(PatientDoctorAssignment.is_active == True)
        ).first()
        if not assignment:
            return None
        return session.get(User, assignment.doctor_id)
    except Exception as e:
        raise
    
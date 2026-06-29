from sqlmodel import Session, select
from typing import Optional, List
from models.patient_doctor import PatientDoctorAssignment
from models.user import User, UserRole
from models.audit_log import ActionType 
from services.crud.audit_log import log_action


def assign_doctor(patient_id: int, doctor_id: int, session: Session,
                  current_user: User) -> PatientDoctorAssignment:
    """Только администратор может назначать врачей."""
    try:
        if current_user.role != UserRole.ADMIN:
           raise ValueError("Admin access required")
        # Проверяем, что пользователи существуют
        patient = session.get(User, patient_id)
        doctor = session.get(User, doctor_id)
        if not patient or not doctor:
            raise ValueError("Patient or doctor not found")
        # Деактивируем старые назначения для этого пациента
        old_assignments = session.exec(
            select(PatientDoctorAssignment)
            .where(PatientDoctorAssignment.patient_id == patient_id)
            .where(PatientDoctorAssignment.is_active == True)
        ).all()
        for a in old_assignments:
            a.is_active = False
            session.add(a)
        # Создаём новое
        assignment = PatientDoctorAssignment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            is_active=True
        )
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
        log_action(session, ActionType.ASSIGN_DOCTOR, current_user.id, target_id=f"patient_{patient_id}_doctor_{doctor_id}")
        return assignment
    except Exception as e:
        raise
        

def get_active_assignments_for_doctor(doctor_id: int, session: Session) -> List[PatientDoctorAssignment]:
    try:
        assignments = session.exec(
            select(PatientDoctorAssignment)
            .where(PatientDoctorAssignment.doctor_id == doctor_id)
            .where(PatientDoctorAssignment.is_active == True)
        ).all()
        return assignments
    except Exception as e:
        raise


def deactivate_assignment(assignment_id: int, session: Session, current_user: User) -> bool:
    """Администратор может деактивировать назначение."""
    try:
        if current_user.role != UserRole.ADMIN:
            raise ValueError("Admin access required")
        assignment = session.get(PatientDoctorAssignment, assignment_id)
        if not assignment:
            return False
        assignment.is_active = False
        session.add(assignment)
        session.commit()
        log_action(session, ActionType.UPDATE_USER, current_user.id, target_id=str(assignment_id), details={"action": "deactivate_assignment"})
        return True
    except Exception as e:
        raise
        
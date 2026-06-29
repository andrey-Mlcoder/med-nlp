from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from database.database import get_session
from models.user import User
from services.crud.user import create_patient, get_user_by_email, get_user_by_id, delete_user
from services.crud.user import get_my_patients as get_my_patients_service
from services.crud.user import get_my_doctor as get_my_doctor_service
from services.crud.wound_image import get_patient_images as get_patient_images_service
from auth.authenticate import authenticate
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)
users_router = APIRouter()
hash_password = HashPassword()


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


@users_router.post('/signup', status_code=status.HTTP_201_CREATED,)
def signup(user_data: dict, session: Session = Depends(get_session)) -> Dict:
    try:
        user = create_patient(user_data, session)
        return {"message": "Patient registered successfully", "user_id": user.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@users_router.post('/signin')
def signin(form_data: OAuth2PasswordRequestForm = Depends(),
                 session=Depends(get_session)) -> Dict[str, str]:
    user = get_user_by_email(form_data.username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not hash_password.verify_hash(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(user.email)
    return {"access_token": access_token, "token_type": "Bearer"}


@users_router.get('/history')
def history(current_user: User = Depends(get_current_user),
                  session: Session = Depends(get_session)) -> List[Dict]:
        images = get_patient_images_service(current_user.id, session, current_user)
        return [
            {
                "id": img.id,
                "upload_date": img.upload_date.isoformat(),
                "area_percent": img.wound_area_percentage,
                "change": img.area_change_percentage,
                "alert": img.is_alert
            }
            for img in images
        ]
    

@users_router.get('/profile')
def profile(current_user: User = Depends(get_current_user)) -> Dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "phone": current_user.phone,
        "date_of_birth": current_user.date_of_birth
    }


@users_router.delete('/profile')
def delete_own_account(current_user: User = Depends(get_current_user),
                             session: Session = Depends(get_session)) -> Dict[str, str]:
    success = delete_user(current_user.id, session, current_user)
    if not success:
        raise HTTPException(404, "User not found")
    return {"message": "Account deleted"}


@users_router.get('/doctor')
def get_my_doctor_endpoint(current_user: User = Depends(get_current_user),
                        session: Session = Depends(get_session)) -> Dict:
    """Для пациента – его активный врач."""
    from services.crud.user import get_my_doctor
    doctor = get_my_doctor_service(session, current_user)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not assigned")
    return {
        "id": doctor.id,
        "email": doctor.email,
        "full_name": doctor.full_name,
        "specialization": doctor.specialization
    }


@users_router.get('/patients')
def get_my_patients_endpoint(current_user: User = Depends(get_current_user),
                          session: Session = Depends(get_session)) -> List:
    """Для врача – список активных пациентов."""
    try:
        patients = get_my_patients_service(session, current_user)
        return [
            {
                "id": p.id,
                "email": p.email,
                "full_name": p.full_name,
                "phone": p.phone,
                "date_of_birth": p.date_of_birth
            }
            for p in patients
        ]
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
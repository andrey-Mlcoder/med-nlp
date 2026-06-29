import pytest
from fastapi.testclient import TestClient
import os
import shutil
import time
from sqlmodel import Session, select
from models.user import User, UserRole
from models.wound_image import WoundImage
from models.wound_analysis import WoundAnalysis
from auth.hash_password import HashPassword


TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123"
TEST_DOCTOR_EMAIL = "doctor@example.com"
TEST_ADMIN_EMAIL = "admin@example.com"

# Health check

def test_health_check(client: TestClient):
    """Проверка health endpoint"""
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


# Аутентификация 

def test_signup_patient(client: TestClient):
    """Регистрация нового пациента."""
    user_data = {
        "email": "new@example.com",
        "full_name": "New Patient",
        "password": "newpass123",
        "phone": "+7 999 123-45-67"
    }
    response = client.post("/api/users/signup", json=user_data)
    assert response.status_code == 201
    assert response.json()["message"] == "Patient registered successfully"
    assert "user_id" in response.json()


def test_signup_duplicate_email(client: TestClient, create_test_patient):
    """Попытка регистрации с существующим email."""
    user_data = {
        "email": TEST_EMAIL,
        "full_name": "Duplicate",
        "password": "pass"
    }
    response = client.post("/api/users/signup", json=user_data)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_signin_patient(client: TestClient, create_test_patient):
    """Вход пациента."""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_signin_wrong_password(client: TestClient, create_test_patient):
    """Вход с неверным паролем."""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_EMAIL, "password": "wrong"}
    )
    assert response.status_code == 401


def test_get_profile(client: TestClient, auth_headers_patient):
    """Получение профиля пациента."""
    response = client.get("/api/users/profile", headers=auth_headers_patient)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["full_name"] == "Test Patient"
    assert data["role"] == "patient"


# Загрузка и результат

def test_upload_image(client: TestClient, auth_headers_patient, test_image):
    """Загрузка изображения пациентом."""
    files = {"file": ("test.png", test_image, "image/png")}
    response = client.post(
        "/api/predict/upload",
        headers=auth_headers_patient,
        files=files,
        params={"notes": "Test upload"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "image_id" in data
    assert data["message"] == "Processing started"


def test_upload_image_without_token(client: TestClient, test_image):
    """Загрузка без токена"""
    files = {"file": ("test.png", test_image, "image/png")}
    response = client.post("/api/predict/upload", files=files)
    assert response.status_code == 401


def test_get_result_processing(client: TestClient, auth_headers_patient, session: Session):
    """Получение результата для изображения без анализа (processing)."""
    patient = session.exec(select(User).where(User.email == TEST_EMAIL)).first()
    image = WoundImage(
        patient_id=patient.id,
        image_path="uploads/dummy.jpg",
        original_filename="dummy.jpg"
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    image_id = image.id

    response = client.get(
        f"/api/predict/result/{image_id}",
        headers=auth_headers_patient
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["image_id"] == image_id


def test_get_result_with_analysis(client: TestClient, auth_headers_patient, session: Session):
    """Получение результата, если анализ уже есть."""
    patient = session.exec(select(User).where(User.email == TEST_EMAIL)).first()
    image = WoundImage(
        patient_id=patient.id,
        image_path="uploads/dummy.jpg",
        original_filename="dummy.jpg",
        wound_area_percentage=0.05,
        is_alert=False
    )
    session.add(image)
    session.commit()
    session.refresh(image)

    analysis = WoundAnalysis(
        wound_image_id=image.id,
        dice_score=0.85,
        model_version="test_v1",
        processing_time_ms=123,
        mask_path="/tmp/mask.png"
    )
    session.add(analysis)
    session.commit()

    response = client.get(
        f"/api/predict/result/{image.id}",
        headers=auth_headers_patient
    )
    assert response.status_code == 200
    data = response.json()
    assert data["image_id"] == image.id
    assert data["area_percent"] == 0.05
    assert data["dice"] == 0.85
    assert data["model"] == "test_v1"


def test_get_overlay_without_mask(client: TestClient, auth_headers_patient, session: Session):
    """Оверлей для изображения без маски -> 404."""
    patient = session.exec(select(User).where(User.email == TEST_EMAIL)).first()
    image = WoundImage(
        patient_id=patient.id,
        image_path="uploads/dummy.jpg",
        original_filename="dummy.jpg"
    )
    session.add(image)
    session.commit()
    session.refresh(image)

    response = client.get(
        f"/api/predict/overlay/{image.id}",
        headers=auth_headers_patient
    )
    assert response.status_code == 404
    assert "Mask not found" in response.json()["detail"]


# Врачебные функции

def test_get_my_patients(client: TestClient, auth_headers_doctor, session: Session):
    """Врач получает список своих пациентов (сначала пустой)."""
    response = client.get("/api/users/patients", headers=auth_headers_doctor)
    assert response.status_code == 200
    assert response.json() == []


def test_assign_doctor_by_admin(client: TestClient, auth_headers_admin, session: Session):
    """Администратор назначает врача пациенту."""
    hash_pwd = HashPassword()
    patient = User(
        email="patient2@example.com",
        hashed_password=hash_pwd.create_hash("pass"),
        full_name="Patient 2",
        role=UserRole.PATIENT
    )
    doctor = session.exec(select(User).where(User.email == TEST_DOCTOR_EMAIL)).first()
    if not doctor:
        doctor = User(
            email=TEST_DOCTOR_EMAIL,
            hashed_password=hash_pwd.create_hash("pass"),
            full_name="Test Doctor",
            role=UserRole.DOCTOR
        )
    session.add(patient)
    session.add(doctor)
    session.commit()
    session.refresh(patient)
    session.refresh(doctor)

    response = client.post(
        "/api/admin/assign-doctor",
        headers=auth_headers_admin,
        params={"patient_id": patient.id, "doctor_id": doctor.id}
    )
    assert response.status_code == 200
    assert "Doctor assigned" in response.json()["message"]


# Админские функции

def test_admin_list_users(client: TestClient, auth_headers_admin):
    """Администратор получает список всех пользователей."""
    response = client.get("/api/admin/users", headers=auth_headers_admin)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_admin_list_users_forbidden(client: TestClient, auth_headers_patient):
    """Пациент не может получить список пользователей."""
    response = client.get("/api/admin/users", headers=auth_headers_patient)
    assert response.status_code == 403


def test_admin_get_audit_logs(client: TestClient, auth_headers_admin):
    """Администратор получает аудит-лог."""
    response = client.get("/api/admin/audit-logs", headers=auth_headers_admin)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# Тесты ролей

def test_patient_cannot_access_doctor_endpoint(client: TestClient, auth_headers_patient):
    """Пациент не может получить список пациентов врача."""
    response = client.get("/api/users/patients", headers=auth_headers_patient)
    assert response.status_code == 403


def test_doctor_can_access_patient_images(client: TestClient, auth_headers_doctor, session: Session):
    """Врач может запросить изображения пациента (пустой список)."""
    patient = User(
        email="patient3@example.com",
        hashed_password=HashPassword().create_hash("pass"),
        full_name="Patient 3",
        role=UserRole.PATIENT
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    response = client.get(
        f"/api/predict/images/patient/{patient.id}",
        headers=auth_headers_doctor
    )
    assert response.status_code == 200
    assert response.json() == []
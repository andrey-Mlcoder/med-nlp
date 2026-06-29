import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from api import app
from database.database import get_session
from auth.authenticate import authenticate
from services.rm.rm import publish_wound_task
from models.user import User, UserRole
from models.patient_doctor import PatientDoctorAssignment
from auth.hash_password import HashPassword
from PIL import Image
import io
import os
import tempfile

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123"
TEST_DOCTOR_EMAIL = "doctor@example.com"
TEST_DOCTOR_PASSWORD = "doc123"
TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "admin123"


def mock_publish_wound_task(image_id, patient_id, image_path, task_id=None):
    """Заглушка для публикации задачи в очередь."""
    print(f"Mock publish task for image {image_id}")
    pass


@pytest.fixture(name="session")
def session_fixture():
    """Тестовая сессия БД (SQLite)"""
    engine = create_engine(
        "sqlite:///testing.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Тестовый клиент с подмененными зависимостями"""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    app.dependency_overrides[publish_wound_task] = mock_publish_wound_task

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_image():
    """Создает тестовое изображение (PNG)."""
    img = Image.new('RGB', (200, 100), color='white')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


@pytest.fixture
def create_test_patient(session: Session):
    """Создает тестового пациента."""
    hash_pwd = HashPassword()
    user = User(
        email=TEST_EMAIL,
        hashed_password=hash_pwd.create_hash(TEST_PASSWORD),
        full_name="Test Patient",
        role=UserRole.PATIENT,
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def create_test_doctor(session: Session):
    """Создает тестового врача."""
    hash_pwd = HashPassword()
    user = User(
        email=TEST_DOCTOR_EMAIL,
        hashed_password=hash_pwd.create_hash(TEST_DOCTOR_PASSWORD),
        full_name="Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
        specialization="Wound Care"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def create_test_admin(session: Session):
    """Создает тестового администратора."""
    hash_pwd = HashPassword()
    user = User(
        email=TEST_ADMIN_EMAIL,
        hashed_password=hash_pwd.create_hash(TEST_ADMIN_PASSWORD),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_headers_patient(client: TestClient, create_test_patient):
    """Возвращает заголовки с токеном для пациента."""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_doctor(client: TestClient, create_test_doctor):
    """Возвращает заголовки с токеном для врача."""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_DOCTOR_EMAIL, "password": TEST_DOCTOR_PASSWORD}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(client: TestClient, create_test_admin):
    """Возвращает заголовки с токеном для администратора."""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
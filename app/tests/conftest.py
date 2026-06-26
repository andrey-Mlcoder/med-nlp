import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from api import app
from database.database import get_session
from auth.authenticate import authenticate
from services.rm.rm import publish_ml_task
from models.user import User
from models.balance import Balance
from PIL import Image
import io

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "123456"


def mock_publish_ml_task(task, session):
    """Заглушка для RabbitMQ"""
    print(f"Mock publish task: {task.task_id}")
    pass


@pytest.fixture(name="session")
def session():
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

    def authenticate_override():
        return TEST_EMAIL

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[authenticate] = authenticate_override
    app.dependency_overrides[publish_ml_task] = mock_publish_ml_task

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def create_test_model(session: Session):
    """Создает тестовую ML модель"""
    from models.model import ML_model

    model = ML_model(
        name="EasyOcr",
        model_type="ocr",
        languages='["ru", "en"]'
    )
    session.add(model)
    session.commit()
    session.refresh(model)
    return model

@pytest.fixture
def test_image():
    """Создает тестовое изображение"""
    img = Image.new('RGB', (200, 100), color='white')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "Test Text 123", fill='black')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


@pytest.fixture
def create_test_user(session: Session, create_test_model):
    """Создает тестового пользователя напрямую в БД"""
    from auth.hash_password import HashPassword
    hash_password = HashPassword()

    user = User(
        username="testuser",
        email=TEST_EMAIL,
        password=hash_password.create_hash(TEST_PASSWORD)
    )

    balance = Balance(amount=100.0)
    user.balance = balance

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, create_test_user):
    """Возвращает заголовки с токеном для тестового пользователя"""
    response = client.post(
        "/api/users/signin",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
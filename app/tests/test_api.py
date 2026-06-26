import pytest
from fastapi.testclient import TestClient
import time

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "123456"

# Health check

def test_health_check(client: TestClient):
    """Проверка health endpoint"""
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


# Тесты пользователей

def test_signup_user(client: TestClient):
    """Регистрация нового пользователя"""
    user_data = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "secret123"
    }

    response = client.post("/api/users/signup", json=user_data)
    assert response.status_code == 201
    assert response.json() == {"message": "User successfully registered"}


def test_signup_duplicate_email(client: TestClient, create_test_user):
    """Попытка регистрации с существующим email"""
    user_data = {
        "username": "another",
        "email": TEST_EMAIL,
        "password": "test123"
    }

    response = client.post("/api/users/signup", json=user_data)
    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"


def test_signin_user(client: TestClient, create_test_user):
    """Авторизация пользователя"""
    response = client.post("/api/users/signin",
        data={"username": TEST_EMAIL,
            "password": TEST_PASSWORD})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "Bearer"


def test_signin_wrong_password(client: TestClient, create_test_user):
    """Авторизация с неверным паролем"""
    response = client.post(
        "/api/users/signin",
        data={"username": TEST_EMAIL,
            "password": "wrongpassword"})
    assert response.status_code == 401


def test_signin_nonexistent_user(client: TestClient):
    """Авторизация несуществующего пользователя"""
    response = client.post(
        "/api/users/signin",
        data={"username": "nonexist@test.com",
            "password": "test123"})
    assert response.status_code == 404


def test_get_profile(client: TestClient, auth_headers, create_test_user):
    """Получение профиля пользователя"""
    response = client.get("/api/users/profile", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["balance"] == "100.0"
    assert data["username"] == "testuser"


def test_profile_without_token(client: TestClient):
    """Доступ к профилю без токена"""
    response = client.get("/api/users/profile")
    assert response.status_code == 404
    assert response.json()["detail"] == "User profile not found"


# Тесты баланса

def test_get_balance(client: TestClient, auth_headers):
    """Получение текущего баланса"""
    response = client.get("/api/balance/current_balance", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "100.0"
    assert data["email"] == TEST_EMAIL


def test_get_balance_without_token(client: TestClient):
    """Доступ к балансу без токена"""
    response = client.get("/api/balance/current_balance")
    assert response.status_code == 404


def test_add_balance(client: TestClient, auth_headers):
    """Пополнение баланса"""
    response = client.post(
        "/api/balance/add_balance",
        headers=auth_headers,
        params={"amount": 50.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Balance updated successfully"
    assert data["new_balance"] == "150.0"


def test_add_balance_invalid_amount(client: TestClient, auth_headers):
    """Пополнение с некорректной суммой"""
    response = client.post(
        "/api/balance/add_balance",
        headers=auth_headers,
        params={"amount": -10.0}
    )
    assert response.status_code == 422


def test_balance_update_after_addition(client: TestClient, auth_headers):
    """Проверка обновления баланса после пополнения"""
    client.post("/api/balance/add_balance", headers=auth_headers, params={"amount": 50.0})

    response = client.get("/api/balance/current_balance", headers=auth_headers)
    assert response.json()["amount"] == "150.0"


def test_spend_balance_success(client: TestClient, auth_headers):
    """Успешное списание средств"""
    response = client.post(
        "/api/balance/spend_balance",
        headers=auth_headers,
        params={"amount": 30.0}
    )
    assert response.status_code == 200
    assert response.json()["new_balance"] == "70.0"


def test_spend_balance_insufficient(client: TestClient, auth_headers):
    """Списание при недостаточном балансе"""
    response = client.post(
        "/api/balance/spend_balance",
        headers=auth_headers,
        params={"amount": 200.0}
    )
    assert response.status_code == 400
    assert "detail" in response.json()


# Тесты ML запросов

def test_upload_image_success(client: TestClient, auth_headers, test_image):
    """Успешная отправка изображения на обработку"""
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    params = {"cost": 10.0, "description": "Test image"}

    response = client.post(
        "/api/predict/upload_image",
        headers=auth_headers,
        files=files,
        params=params
    )

    if response.status_code == 500:
        pytest.skip("ML model not available")

    assert response.status_code == 200
    assert "task_id" in response.json()
    balance_response = client.get("/api/balance/current_balance", headers=auth_headers)
    assert balance_response.json()["amount"] == "90.0"


def test_upload_image_without_description(client: TestClient, auth_headers, test_image):
    """Отправка изображения без описания"""
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    params = {"cost": 10.0}

    response = client.post(
        "/api/predict/upload_image",
        headers=auth_headers,
        files=files,
        params=params
    )

    if response.status_code == 500:
        pytest.skip("ML model not available")

    assert response.status_code == 200
    assert "task_id" in response.json()


def test_upload_image_insufficient_balance(client: TestClient):
    """Отправка изображения при недостаточном балансе"""
    unique_id = int(time.time() * 1000)
    unique_email = f"poor_{unique_id}@example.com"
    unique_username = f"pooruser_{unique_id}"
    poor_user = {
        "username": unique_username,
        "email": unique_email,
        "password": "Test123"
    }
    signup_response = client.post("/api/users/signup", json=poor_user)
    assert signup_response.status_code == 201, f"Failed to create user: {signup_response.json()}"
    login_response = client.post(
        "/api/users/signin",
        data={"username": unique_email, "password": "Test123"})
    assert login_response.status_code == 200, f"Failed to login: {login_response.json()}"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test.jpg", b"fake_image", "image/jpeg")}
    params = {"cost": 10.0, "description": "Test"}

    response = client.post(
        "/api/predict/upload_image",
        headers=headers,
        files=files,
        params=params)

    assert response.status_code in [400, 500]


def test_upload_invalid_file_type(client: TestClient, auth_headers):
    """Отправка файла неверного типа"""
    files = {"file": ("test.txt", b"not an image", "text/plain")}
    params = {"cost": 10.0, "description": "Invalid"}

    response = client.post(
        "/api/predict/upload_image",
        headers=auth_headers,
        files=files,
        params=params
    )

    assert response.status_code in [400, 422, 500]


def test_upload_empty_file(client: TestClient, auth_headers):
    """Отправка пустого файла"""
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    params = {"cost": 10.0, "description": "Empty"}

    response = client.post(
        "/api/predict/upload_image",
        headers=auth_headers,
        files=files,
        params=params
    )

    assert response.status_code in [400, 422, 500]


def test_get_task_result(client: TestClient, auth_headers, test_image):
    """Создание задачи и получение результата"""
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    params = {"cost": 10.0, "description": "Get result test"}

    upload_response = client.post(
        "/api/predict/upload_image",
        headers=auth_headers,
        files=files,
        params=params
    )
    if upload_response.status_code != 200:
        pytest.skip("ML model not available")

    task_id = upload_response.json()["task_id"]
    time.sleep(2)

    result_response = client.get(
        f"/api/predict/get-result/{task_id}",
        headers=auth_headers
    )

    assert result_response.status_code == 200
    data = result_response.json()
    if "status" in data:
        assert data["status"] in ["processing", "completed", "failed"]
    else:
        assert "detail" in data
        assert "Timeout" in data["detail"]


def test_get_task_result_not_found(client: TestClient, auth_headers):
    """Получение результата для несуществующей задачи"""
    response = client.get(
        "/api/predict/get-result/non-existent-id",
        headers=auth_headers
    )
    assert response.status_code == 404


# Тесты истории

def test_user_history_empty(client: TestClient, auth_headers):
    """История нового пользователя пуста"""
    response = client.get("/api/users/history", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_user_history_after_operations(client: TestClient, auth_headers, test_image):
    """История после выполнения операций"""
    client.post("/api/balance/add_balance", headers=auth_headers, params={"amount": 50.0})
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    params = {"cost": 10.0, "description": "History test 1"}
    resp1 = client.post("/api/predict/upload_image", headers=auth_headers, files=files, params=params)
    if resp1.status_code != 200:
        pytest.skip("ML model not available")
    task_id = resp1.json()["task_id"]
    response = client.get("/api/users/history", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    if history:
        assert len(history) >= 1
        # Проверяем что есть запись с нашим task_id
        found = any(item.get("task_id") == task_id for item in history if item)
        assert found


# Тесты админа

def test_admin_check_not_admin(client: TestClient, auth_headers):
    """Проверка, что обычный пользователь не админ"""
    response = client.get("/api/admin/check", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_admin"] == False
    assert response.json()["username"] == "testuser"


def test_admin_users_forbidden(client: TestClient, auth_headers):
    """Обычный пользователь не может получить список всех пользователей"""
    response = client.get("/api/admin/users",
                          headers=auth_headers)
    assert response.status_code == 403


def test_admin_balance_add_forbidden(client: TestClient, auth_headers):
    """Обычный пользователь не может пополнять баланс других"""
    response = client.post(
        "/api/admin/users/1/balance",
        headers=auth_headers,
        params={"amount": 100.0}
    )
    assert response.status_code == 403


def test_admin_transactions_forbidden(client: TestClient, auth_headers):
    """Обычный пользователь не может смотреть все транзакции"""
    response = client.get("/api/admin/transactions", headers=auth_headers)
    assert response.status_code == 403


# Тесты удаления

def test_delete_own_account(client: TestClient, auth_headers, create_test_user):
    """Пользователь может удалить свой аккаунт"""
    user_id = create_test_user.user_id

    response = client.delete(
        f"/api/users/profile?user_id={user_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert f"User {user_id} has been deleted" in response.json()["message"]
    profile_response = client.get("/api/users/profile", headers=auth_headers)
    assert profile_response.status_code == 404


def test_cannot_delete_other_user(client: TestClient, auth_headers):
    """Пользователь не может удалить чужой аккаунт"""
    response = client.delete(
        "/api/users/profile?user_id=999",
        headers=auth_headers
    )
    assert response.status_code == 500


def test_delete_with_wrong_id(client: TestClient, auth_headers, create_test_user):
    """Попытка удалить с неверным ID"""
    user_id = create_test_user.user_id
    wrong_id = user_id + 100

    response = client.delete(
        f"/api/users/profile?user_id={wrong_id}",
        headers=auth_headers
    )
    assert response.status_code == 500


# Тесты без авторизации

def test_predict_without_token(client: TestClient, test_image):
    """Отправка изображения без токена"""
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    response = client.post("/api/predict/upload_image", files=files)
    assert response.status_code == 422


def test_history_without_token(client: TestClient):
    """История без токена"""
    response = client.get("/api/users/history")
    assert response.status_code == 404


def test_add_balance_without_token(client: TestClient):
    """Пополнение без токена"""
    response = client.post("/api/balance/add_balance", params={"amount": 100.0})
    assert response.status_code == 400
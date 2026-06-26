import gradio as gr
import requests
from PIL import Image
import io

# Конфигурация
API_BASE_URL = "http://localhost:8080/api"


def make_request(
        method: str,
        endpoint: str,
        token: str = None,
        json_data: dict = None,
        form_data: dict = None,
        files: dict = None,
        params: dict = None
) -> tuple[bool, any]:
    """Универсальная функция для API запросов"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{API_BASE_URL}{endpoint}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "POST":
            if files:
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    files=files,
                    timeout=30
                )
            elif json_data:
                headers["Content-Type"] = "application/json"
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=10
                )
            elif form_data:
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    data=form_data,
                    timeout=10
                )
            else:
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    timeout=10
                )
        elif method.upper() == "DELETE":
            response = requests.delete(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
        else:
            return False, f"Unsupported method: {method}"

        if response.status_code in [200, 201, 204]:
            return True, response.json()
        else:
            try:
                error_data = response.json()
                return False, error_data.get("detail", error_data)
            except:
                return False, response.text

    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API server"
    except Exception as e:
        return False, str(e)


# Функции пользователей

def login(username: str, password: str, session_state):
    """Авторизация через /api/users/signin"""

    if not username or not password:
        return "❌ Введите email и пароль", session_state, gr.update(visible=False)

    login_data = {
        "username": username,
        "password": password
    }

    success, result = make_request("POST", "/users/signin", form_data=login_data)

    if success:
        token = result.get("access_token")
        if token:
            session_state["token"] = token
            session_state["user"] = username

            # Получаем профиль
            prof_success, profile = make_request("GET", "/users/profile", token=token)

            if prof_success:
                session_state["profile"] = profile

                # Проверяем, является ли админом
                admin_success, admin_check = make_request("GET", "/admin/check", token=token)
                if admin_success:
                    session_state["is_admin"] = admin_check.get("is_admin", False)
                return f"✅ Добро пожаловать, {profile.get('username', username)}!", session_state, gr.update(
                    visible=True)
            return "✅ Вход выполнен!", session_state, gr.update(visible=True)
    return f"❌ Ошибка: {result}", session_state, gr.update(visible=False)


def register(username: str, email: str, password: str, session_state):
    """Регистрация через /api/users/signup"""
    if not username or not email or not password:
        return "❌ Заполните все поля", session_state

    user_data = {
        "username": username,
        "email": email,
        "password": password
    }

    success, result = make_request("POST", "/users/signup", json_data=user_data)

    if success:
        return "✅ Регистрация успешна! Теперь войдите.", session_state
    else:
        return f"❌ Ошибка: {result}", session_state


def logout(session_state):
    """Выход из системы"""
    session_state.clear()
    return "👋 Вы вышли из системы", session_state, gr.update(visible=False)


def get_balance(session_state):
    """Получение баланса через /api/balance/current_balance"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/balance/current_balance", token=session_state["token"])

    if success:
        amount = result.get('amount', '0')
        return f"💰 Баланс: {amount} кредитов"
    else:
        return f"❌ Ошибка: {result}"


def topup_balance(amount: float, session_state):
    """Пополнение баланса через /api/balance/add_balance"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    if amount <= 0:
        return "❌ Сумма должна быть положительной"

    success, result = make_request("POST", "/balance/add_balance", token=session_state["token"],
                                   params={"amount": amount})

    if success:
        new_balance = result.get('new_balance', '0')
        return f"✅ Пополнено! Новый баланс: {new_balance} кредитов"
    else:
        return f"❌ Ошибка: {result}"


def predict_image(image, description: str, session_state):
    """Отправка изображения через /api/predict/upload_image"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему", None

    if image is None:
        return "❌ Выберите изображение", None

    # Конвертируем PIL Image в bytes
    img_bytes = io.BytesIO()
    if image.mode != 'RGB':
        image = image.convert('RGB')

    image.save(img_bytes, format='JPEG', quality=95)
    img_bytes = img_bytes.getvalue()

    # Создаем файл для отправки
    files = {
        'file': ('image.jpg', img_bytes, 'image/jpeg')
    }

    params = {
        'cost': '10.0',
        'description': description or "Запрос из Gradio"
    }

    success, result = make_request("POST", "/predict/upload_image", token=session_state["token"],
                                   files=files, params=params)

    if success:
        task_id = result.get("task_id")
        return f"✅ Задача создана! ID: {task_id}", task_id
    else:
        return f"❌ Ошибка: {result}", None


def get_task_result(task_id: str, session_state):
    """Получение результата через /api/predict/get-result/{task_id}"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    if not task_id:
        return "❌ Введите ID задачи"

    success, result = make_request("GET", f"/predict/get-result/{task_id}", token=session_state["token"])

    if success:
        status = result.get("status", "unknown")
        prediction = result.get("prediction", "")

        if status == "completed":
            return f"✅ РЕЗУЛЬТАТ:\n{prediction}"
        elif status == "failed":
            return f"❌ Задача не выполнена"
        elif status == "processing":
            return f"⏳ Задача в обработке..."
        else:
            return f"📊 Статус: {status}"
    else:
        return f"❌ Ошибка: {result}"


def get_history(session_state):
    """Получение истории через /api/users/history"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/users/history", token=session_state["token"])

    if success:
        if not result:
            return "📭 История пуста"

        output = "📊 ИСТОРИЯ ОПЕРАЦИЙ:\n"
        output += "=" * 60 + "\n"
        for item in result[:15]:
            created_at = item.get('created_at', 'N/A')[:16] if item.get('created_at') else 'N/A'
            output += f"📅 {created_at}\n"
            output += f"📝 {item.get('description', 'N/A')}\n"
            output += f"💰 Стоимость: {item.get('cost', 0)} кредитов\n"
            output += f"🆔 Задача: {item.get('task_id', 'N/A')}\n"
            output += "-" * 40 + "\n"

        return output
    else:
        return f"❌ Ошибка: {result}"


def get_profile(session_state):
    """Получение профиля через /api/users/profile"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/users/profile", token=session_state["token"])

    if success:
        output = f"👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:\n"
        output += "=" * 40 + "\n"
        output += f"📧 Email: {result.get('email', 'N/A')}\n"
        output += f"👤 Имя: {result.get('username', 'N/A')}\n"
        output += f"💰 Баланс: {result.get('balance', '0')} кредитов\n"
        output += f"🆔 ID: {result.get('user_id', 'N/A')}\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def delete_my_account(session_state):
    """Удаление собственного аккаунта пользователем"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему", session_state

    user_id = session_state.get("profile", {}).get("user_id")
    if not user_id:
        return "❌ Не удалось определить ID пользователя", session_state

    user_id_int = int(user_id)
    success, result = make_request(
        "DELETE",
        f"/users/profile?user_id={user_id_int}",
        token=session_state["token"]
    )
    if success:
        session_state.clear()
        return "✅ Ваш аккаунт успешно удален. До свидания!", session_state
    else:
        error_msg = result
        if isinstance(result, dict) and "detail" in result:
            error_msg = result["detail"]
        return f"❌ Ошибка при удалении аккаунта: {error_msg}", session_state


# Функции админа

def get_all_users_admin(session_state):
    """Просмотр всех пользователей через /api/admin/users"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/admin/users", token=session_state["token"])

    if success:
        if not result:
            return "📭 Нет пользователей"

        output = "👥 ВСЕ ПОЛЬЗОВАТЕЛИ:\n"
        output += "=" * 70 + "\n"
        for i, user in enumerate(result, 1):
            output += f"{i}. ID: {user.get('user_id')}\n"
            output += f"   👤 Имя: {user.get('username')}\n"
            output += f"   📧 Email: {user.get('email')}\n"
            output += f"   💰 Баланс: {user.get('balance')} кредитов\n"
            output += f"   📊 Задач: {user.get('tasks_count', 0)}\n"
            output += f"   📅 Создан: {user.get('created_at', 'N/A')[:10]}\n"
            output += "-" * 50 + "\n"

        return output
    else:
        return f"❌ Ошибка: {result}"


def admin_add_balance(user_id: int, amount: float, session_state):
    """Пополнение баланса пользователя админом через /api/admin/users/{user_id}/balance"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    if amount <= 0:
        return "❌ Сумма должна быть положительной"

    if not user_id or user_id <= 0:
        return "❌ Введите корректный ID пользователя"

    success, result = make_request("POST", f"/admin/users/{user_id}/balance", token=session_state["token"],
                                   params={"amount": amount})

    if success:
        return f"✅ УСПЕШНО!\nПользователь: {result.get('username')}\nСумма: +{amount} кредитов\nНовый баланс: {result.get('new_balance')} кредитов"
    else:
        return f"❌ Ошибка: {result}"


def moderate_deposit(user_id: int, amount: float, decision: str, session_state):
    """Модерация пополнения через /api/admin/moderate-deposit"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    if amount <= 0:
        return "❌ Сумма должна быть положительной"

    if not user_id or user_id <= 0:
        return "❌ Введите корректный ID пользователя"

    success, result = make_request("POST", "/admin/moderate-deposit", token=session_state["token"], params={
        "user_id": user_id,
        "amount": amount,
        "decision": decision
    })

    if success:
        status = result.get('status', 'unknown')
        message = result.get('message', '')

        if status == 'approved':
            return f"✅ ОДОБРЕНО!\n{message}\nНовый баланс: {result.get('new_balance')} кредитов"
        elif status == 'rejected':
            return f"❌ ОТКЛОНЕНО!\n{message}"
        else:
            return f"ℹ️ {message}"
    else:
        return f"❌ Ошибка: {result}"


def get_all_transactions_admin(session_state):
    """Просмотр всех транзакций через /api/admin/transactions"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/admin/transactions", token=session_state["token"], params={"limit": 50})

    if success:
        if not result:
            return "📭 Нет транзакций"

        output = "💰 ВСЕ ТРАНЗАКЦИИ:\n"
        output += "=" * 70 + "\n"
        for i, t in enumerate(result, 1):
            amount = t.get('amount')
            sign = "+" if amount and amount > 0 else ""
            output += f"{i}. ID транзакции: {t.get('transaction_id')}\n"
            output += f"   👤 Пользователь: {t.get('username')} (ID: {t.get('user_id')})\n"
            output += f"   💵 Сумма: {sign}{amount} кредитов\n"
            output += f"   📅 Дата: {t.get('created_at', 'N/A')[:16]}\n"
            output += "-" * 50 + "\n"

        return output
    else:
        return f"❌ Ошибка: {result}"


def get_admin_history(session_state):
    """Просмотр истории действий администратора через /api/admin/history"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    success, result = make_request("GET", "/admin/history", token=session_state["token"])

    if success:
        history = result.get("history", [])

        if not history:
            return "📭 История действий пуста"

        output = f"📋 ИСТОРИЯ ДЕЙСТВИЙ АДМИНА {result.get('username')}:\n"
        output += "=" * 70 + "\n"

        for i, action in enumerate(history[:30], 1):
            timestamp = action.get('timestamp', '')[:16] if action.get('timestamp') else 'N/A'
            output += f"{i}. 🕐 {timestamp}\n"
            output += f"   👤 Пользователь ID: {action.get('user_id')}\n"
            output += f"   💰 Сумма: +{action.get('amount')} кредитов\n"
            if action.get('description'):
                output += f"   📝 Описание: {action.get('description')}\n"
            output += "-" * 50 + "\n"

        return output
    else:
        return f"❌ Ошибка: {result}"


def admin_delete_user(user_id: float, session_state):
    """Удаление пользователя администратором"""
    if not session_state.get("token"):
        return "❌ Сначала войдите в систему"

    if not user_id or user_id <= 0:
        return "❌ Введите корректный ID пользователя"

    user_id_int = int(user_id)
    success, result = make_request(
        "DELETE",
        f"/admin/users/{user_id_int}",
        token=session_state["token"]
    )

    if success:
        return f"✅ Пользователь ID {user_id_int} успешно удален администратором!"
    else:
        error_msg = result
        if isinstance(result, dict) and "detail" in result:
            error_msg = result["detail"]
        return f"❌ Ошибка: {error_msg}"


# Информация о пользователе
user_info = gr.HTML("""
<div style="text-align: center; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
        <p>👤 Статус: Не авторизован</p>
</div>
""")

def update_user_info(session_state):
    if session_state.get("profile"):
        username = session_state["profile"].get("username", "Unknown")
        is_admin = session_state.get("is_admin", False)
        admin_badge = " 👑 (Администратор)" if is_admin else ""
        return f"""
        <div style="text-align: center; padding: 10px; background-color: #e3f2fd; border-radius: 5px;">
            <p>👤 Пользователь: {username}{admin_badge}</p>
        </div>
        """
    else:
        return """
        <div style="text-align: center; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
            <p>👤 Статус: Не авторизован</p>
        </div>
        """

def update_admin_visibility(session_state):
    """Обновляет видимость админского контента"""
    is_admin = session_state.get("is_admin", False)
    print(f"👑 Updating admin visibility: {is_admin}")
    return [
        gr.update(visible=is_admin),  # admin_content
        gr.update(visible=not is_admin)  # non_admin_msg
    ]


# Интерфейс Gradio

custom_css = """
.gradio-container {
    max-width: 1400px !important;
    margin: 20px auto !important;
}
.admin-badge {
    background-color: #dc3545;
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 12px;
    margin-left: 10px;
}
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown("""
    # 🤖 ML SERVICE INTERFACE

    Сервис распознавания текста на изображениях с помощью EasyOCR
    """)

    # Состояние сессии
    session_state = gr.State({})

    with gr.Tabs() as tabs:
        # Первая вкладка - Авторизация
        with gr.TabItem("🔐 Вход / Регистрация", id=0):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Вход в систему")
                    login_email = gr.Textbox(label="Email", placeholder="email@example.com")
                    login_pass = gr.Textbox(label="Пароль", type="password")
                    login_btn = gr.Button("Войти", variant="primary")

                with gr.Column():
                    gr.Markdown("### Регистрация")
                    reg_name = gr.Textbox(label="Имя пользователя", placeholder="username")
                    reg_email = gr.Textbox(label="Email", placeholder="email@example.com")
                    reg_pass = gr.Textbox(label="Пароль", type="password")
                    reg_btn = gr.Button("Зарегистрироваться", variant="secondary")

            logout_btn = gr.Button("🚪 Выйти", variant="stop")
            auth_output = gr.Textbox(label="Статус", lines=3)

        # Вторая вкладка - Баланс
        with gr.TabItem("💰 Баланс"):
            with gr.Row():
                with gr.Column():
                    check_balance_btn = gr.Button("Проверить баланс")
                    balance_output = gr.Textbox(label="Текущий баланс", lines=2)

                with gr.Column():
                    topup_amount = gr.Number(label="Сумма пополнения", value=100, minimum=1)
                    topup_btn = gr.Button("Пополнить", variant="primary")

            check_balance_btn.click(get_balance, [session_state], [balance_output])
            topup_btn.click(topup_balance, [topup_amount, session_state], [balance_output])

        # Вкладка 3 - ML-запрос
        with gr.TabItem("🔍 Распознать текст"):
            with gr.Row():
                with gr.Column():
                    image_input = gr.Image(type="pil", label="Загрузите изображение")
                    image_desc = gr.Textbox(label="Описание", placeholder="Опишите изображение")
                    predict_btn = gr.Button("Отправить", variant="primary")

                with gr.Column():
                    predict_output = gr.Textbox(label="Результат", lines=5)
                    last_task_id = gr.Textbox(label="ID последней задачи", interactive=False)

            predict_btn.click(predict_image, [image_input, image_desc, session_state], [predict_output, last_task_id])

        # Вкладка 4 - Результаты
        with gr.TabItem("📋 Результаты"):
            with gr.Row():
                with gr.Column():
                    task_id_input = gr.Textbox(label="ID задачи", placeholder="Введите ID задачи")
                    check_result_btn = gr.Button("Получить результат", variant="secondary")

                with gr.Column():
                    history_btn = gr.Button("История операций")

            result_output = gr.Textbox(label="Результат", lines=10)

            check_result_btn.click(get_task_result, [task_id_input, session_state], [result_output])
            history_btn.click(get_history, [session_state], [result_output])

        # Вкладка 5 - Профиль
        with gr.TabItem("👤 Профиль"):
            profile_btn = gr.Button("👤 Показать профиль", variant="primary")
            profile_output = gr.Textbox(label="Информация о профиле", lines=6)
            with gr.Row():
                with gr.Column():
                    delete_account_btn = gr.Button(
                        "🗑️ Удалить аккаунт",
                        variant="stop",
                        visible=False
                    )

                    delete_account_output = gr.Textbox(label="Результат удаления", lines=2)

            profile_btn.click(get_profile, [session_state], [profile_output])

            # Удаление аккаунта
            delete_account_btn.click(
                delete_my_account,
                [session_state],
                [delete_account_output, session_state]
            ).then(
                update_user_info,
                [session_state],
                [user_info]
            ).then(
                lambda: gr.update(visible=False),
                None,
                delete_account_btn
            )

        # Вкладка 6 - Панель админа
        with gr.TabItem("👑 Админ панель") as admin_tab:
            # Контент для админов (скрыт по умолчанию)
            admin_content = gr.Column(visible=False)

            with admin_content:
                with gr.Tabs():
                    # Подвкладка 1: Все пользователи
                    with gr.TabItem("👥 Все пользователи"):
                        get_users_btn = gr.Button("📋 Показать всех пользователей", variant="primary")
                        users_output = gr.Textbox(label="Список пользователей", lines=20)
                        get_users_btn.click(get_all_users_admin, [session_state], [users_output])

                    # Подвкладка 2: Пополнить баланс
                    with gr.TabItem("💰 Пополнить баланс"):
                        with gr.Row():
                            with gr.Column():
                                admin_user_id = gr.Number(label="ID пользователя", value=1, minimum=1)
                                admin_amount = gr.Number(label="Сумма пополнения", value=100, minimum=1)
                                admin_add_btn = gr.Button("✅ Пополнить", variant="primary")
                            with gr.Column():
                                admin_add_output = gr.Textbox(label="Результат", lines=6)
                        admin_add_btn.click(admin_add_balance, [admin_user_id, admin_amount, session_state],
                                            [admin_add_output])

                    # Подвкладка 3: Все транзакции
                    with gr.TabItem("📊 Все транзакции"):
                        get_trans_btn = gr.Button("📋 Показать все транзакции", variant="primary")
                        trans_output = gr.Textbox(label="Список транзакций", lines=20)
                        get_trans_btn.click(get_all_transactions_admin, [session_state], [trans_output])

                    # Подвкладка 4: История админа
                    with gr.TabItem("📜 История действий"):
                        get_admin_hist_btn = gr.Button("📋 Показать историю", variant="primary")
                        admin_hist_output = gr.Textbox(label="История действий", lines=20)
                        get_admin_hist_btn.click(get_admin_history, [session_state], [admin_hist_output])

                   # Подвкладка 5: Удалить пользователя
                    with gr.TabItem("🗑️ Удалить пользователя"):
                        with gr.Row():
                            with gr.Column():
                                admin_delete_user_id = gr.Number(
                                    label="ID пользователя для удаления",
                                    value=1,
                                    minimum=1
                                )
                                admin_delete_btn = gr.Button(
                                    "🗑️ Удалить пользователя",
                                    variant="stop"
                                )
                            with gr.Column():
                                admin_delete_output = gr.Textbox(
                                    label="Результат",
                                    lines=4
                                )

                        admin_delete_btn.click(
                            admin_delete_user,
                            [admin_delete_user_id, session_state],
                            [admin_delete_output]
                        )

                        gr.Markdown("""
                        ⚠️ **Внимание!** Удаление пользователя необратимо.
                        Все задачи и транзакции пользователя также будут удалены.
                        Это действие может выполнить только администратор.
                        """)

            # Сообщение для не-админов (видно по умолчанию)
            non_admin_msg = gr.Column(visible=True)
            with non_admin_msg:
                gr.Markdown("""
                ### 🔒 Доступ ограничен
                Эта вкладка доступна только администраторам.
                """)

    # Информация о пользователе
    user_info = gr.HTML("""
    <div style="text-align: center; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
         <p>👤 Статус: Не авторизован</p>
    </div>
    """)

    # Кнопка входа
    login_btn.click(
        login,
        [login_email, login_pass, session_state],
        [auth_output, session_state, delete_account_btn]
    ).then(
        update_user_info,
        [session_state],
        [user_info]
    ).then(
        update_admin_visibility,
        [session_state],
        [admin_content, non_admin_msg]
    )

    # Кнопка выхода
    logout_btn.click(
        logout,
        [session_state],
        [auth_output, session_state, delete_account_btn]
    ).then(
        update_user_info,
        [session_state],
        [user_info]
    ).then(
        update_admin_visibility,
        [session_state],
        [admin_content, non_admin_msg]
    )

    # Кнопка регистрации
    reg_btn.click(
        register,
        [reg_name, reg_email, reg_pass, session_state],
        [auth_output, session_state]
    ).then(
        update_user_info,
        [session_state],
        [user_info]
    )

    demo.load(
        fn=update_admin_visibility,
        inputs=[session_state],
        outputs=[admin_content, non_admin_msg]
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
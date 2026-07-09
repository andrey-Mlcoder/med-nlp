import gradio as gr
import requests
from PIL import Image
import io
import os

# Конфигурация — адрес API (в Docker: http://app:8080/api)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api")

def make_request(
        method: str,
        endpoint: str,
        token: str = None,
        json_data: dict = None,
        form_data: dict = None,
        files: dict = None,
        params: dict = None
) -> tuple[bool, any]:
    """Универсальная функция для API запросов."""
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
                    url, headers=headers, params=params, files=files, timeout=30
                )
            elif json_data:
                headers["Content-Type"] = "application/json"
                response = requests.post(
                    url, headers=headers, params=params, json=json_data, timeout=10
                )
            elif form_data:
                response = requests.post(
                    url, headers=headers, params=params, data=form_data, timeout=10
                )
            else:
                response = requests.post(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "PATCH":
            if json_data:
                headers["Content-Type"] = "application/json"
                response = requests.patch(url, headers=headers, params=params, json=json_data, timeout=10)
        else:
            return False, f"Unsupported method: {method}"

        if response.status_code in [200, 201, 204]:
            return True, response.json() if response.text else {}
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


# ===================== Аутентификация =====================
def login(username: str, password: str, session_state):
    """Авторизация через /api/users/signin (OAuth2)."""
    if not username or not password:
        return "❌ Введите email и пароль", session_state, gr.update(visible=False)

    form_data = {"username": username, "password": password}
    success, result = make_request("POST", "/users/signin", form_data=form_data)

    if success:
        token = result.get("access_token")
        if token:
            session_state["token"] = token
            session_state["user"] = username

            # Получаем профиль
            prof_success, profile = make_request("GET", "/users/profile", token=token)
            if prof_success:
                session_state["profile"] = profile
                role = profile.get("role", "patient")
                session_state["role"] = role
                return f"✅ Добро пожаловать, {profile.get('full_name', username)}! Роль: {role}", session_state, gr.update(visible=True)
            return "✅ Вход выполнен!", session_state, gr.update(visible=True)
    return f"❌ Ошибка: {result}", session_state, gr.update(visible=False)


def register(email: str, full_name: str, password: str, phone: str, session_state):
    """Регистрация нового пациента через /api/users/signup."""
    if not email or not full_name or not password:
        return "❌ Заполните все обязательные поля", session_state

    user_data = {
        "email": email,
        "full_name": full_name,
        "password": password,
        "phone": phone or None
    }

    success, result = make_request("POST", "/users/signup", json_data=user_data)

    if success:
        return "✅ Регистрация успешна! Теперь войдите.", session_state
    else:
        return f"❌ Ошибка: {result}", session_state


def logout(session_state):
    """Выход из системы."""
    session_state.clear()
    return "👋 Вы вышли из системы", session_state, gr.update(visible=False)


# ===================== Пациентские функции =====================
def upload_wound_image(image, notes, session_state):
    """Загрузка изображения раны."""
    if not session_state.get("token"):
        return "❌ Сначала войдите", None

    if image is None:
        return "❌ Выберите изображение", None

    img_bytes = io.BytesIO()
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image.save(img_bytes, format='JPEG', quality=95)
    img_bytes = img_bytes.getvalue()

    files = {'file': ('image.jpg', img_bytes, 'image/jpeg')}
    params = {'notes': notes or ""}

    success, result = make_request("POST", "/predict/upload", token=session_state["token"],
                                   files=files, params=params)

    if success:
        image_id = result.get("image_id")
        return f"✅ Изображение загружено! ID: {image_id}", image_id
    else:
        return f"❌ Ошибка: {result}", None


def get_result(image_id, session_state):
    """Получение результата анализа."""
    if not session_state.get("token"):
        return "❌ Сначала войдите", None

    if not image_id:
        return "❌ Введите ID изображения", None

    success, result = make_request("GET", f"/predict/result/{image_id}",
                                   token=session_state["token"])

    if success:
        output = f"📊 Результат для изображения {image_id}\n"
        output += "=" * 40 + "\n"
        output += f"📅 Дата загрузки: {result.get('upload_date', 'N/A')}\n"
        output += f"🟢 Площадь раны: {result.get('area_percent', 0)*100:.2f}%\n"
        if result.get('area_change') is not None:
            change = result.get('area_change')
            sign = "+" if change > 0 else ""
            output += f"📈 Изменение: {sign}{change:.1f}%\n"
        output += f"🚨 Алерт: {'Да' if result.get('alert') else 'Нет'}\n"
        if result.get('analysis'):
            analysis = result['analysis']
            output += f"🧠 Модель: {analysis.get('model_version', 'N/A')}\n"
            output += f"⏱️ Время обработки: {analysis.get('processing_time_ms', 0)} мс\n"
            if analysis.get('dice_score') is not None:
                output += f"🎯 Dice: {analysis['dice_score']:.4f}\n"
            if analysis.get('doctor_notes'):
                output += f"📝 Заметки врача: {analysis['doctor_notes']}\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def get_overlay(image_id, color, thickness, show_area, session_state):
    """Получение оверлея с контуром маски."""
    if not session_state.get("token"):
        return None, "❌ Сначала войдите"
    if not image_id:
        return None, "❌ Введите ID изображения"

    params = {
        "color": color,
        "thickness": thickness,
        "show_area": str(show_area).lower()
    }
    headers = {"Authorization": f"Bearer {session_state['token']}"}
    url = f"{API_BASE_URL}/predict/overlay/{image_id}"

    try:
        resp = requests.get(url, headers=headers, params=params, stream=True, timeout=10)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)), "✅ Оверлей получен"
        else:
            return None, f"❌ Ошибка: {resp.text}"
    except Exception as e:
        return None, f"❌ Ошибка: {str(e)}"


def get_patient_history(session_state):
    """История загрузок пациента."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/users/history", token=session_state["token"])
    if success:
        if not result:
            return "📭 Нет загруженных изображений"
        output = "📋 ИСТОРИЯ ЗАГРУЗОК:\n"
        output += "=" * 50 + "\n"
        for item in result[:20]:
            output += f"🆔 {item['id']} | {item['upload_date'][:16]}\n"
            area = item.get('area_percent') or 0
            output += f"   Площадь: {area*100:.2f}% | "
            output += f"Изменение: {item.get('change', 'N/A')}\n"
            output += "-" * 30 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def get_profile(session_state):
    """Получение профиля пользователя через /api/users/profile."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/users/profile", token=session_state["token"])
    if success:
        output = f"👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:\n"
        output += "=" * 40 + "\n"
        output += f"📧 Email: {result.get('email', 'N/A')}\n"
        output += f"👤 Имя: {result.get('full_name', 'N/A')}\n"
        output += f"🆔 ID: {result.get('id', 'N/A')}\n"
        output += f"📞 Телефон: {result.get('phone', 'N/A')}\n"
        output += f"🎂 Дата рождения: {result.get('date_of_birth', 'N/A')}\n"
        output += f"🔑 Роль: {result.get('role', 'N/A')}\n"
        return output
    else:
        return f"❌ Ошибка: {result}"
        
        
def get_my_doctor(session_state):
    """Получение назначенного врача пациента."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/users/doctor", token=session_state["token"])
    if success and result:
        return f"👨‍⚕️ Ваш врач: {result.get('full_name')} ({result.get('email')})"
    else:
        return "❌ Врач не назначен"


# ===================== Врачебные функции =====================
def get_my_patients(session_state):
    """Список пациентов врача."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/users/patients", token=session_state["token"])
    if success:
        if not result:
            return "📭 У вас нет активных пациентов"
        output = "👥 МОИ ПАЦИЕНТЫ:\n"
        output += "=" * 40 + "\n"
        for p in result:
            output += f"🆔 {p['id']} | {p['full_name']} ({p['email']})\n"
            output += f"   Телефон: {p.get('phone', 'N/A')}\n"
            output += "-" * 30 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def get_patient_images(patient_id, session_state):
    """Получить все изображения конкретного пациента (для врача)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    if not patient_id:
        return "❌ Введите ID пациента"

    success, result = make_request("GET", f"/predict/images/patient/{patient_id}",
                                   token=session_state["token"])
    if success:
        if not result:
            return "📭 Нет изображений у пациента"
        output = f"📷 ИЗОБРАЖЕНИЯ ПАЦИЕНТА {patient_id}:\n"
        output += "=" * 40 + "\n"
        for img in result:
            output += f"🆔 {img['id']} | {img['upload_date'][:16]}\n"
            output += f"   Площадь: {img.get('wound_area_percentage', 0)*100:.2f}%\n"
            output += f"   Алерт: {'Да' if img.get('is_alert') else 'Нет'}\n"
            output += "-" * 30 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def update_analysis(analysis_id, doctor_notes, recommendation, follow_up_days, session_state):
    """Обновить анализ (добавить заметки, рекомендации)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    if not analysis_id:
        return "❌ Введите ID анализа"

    data = {
        "doctor_notes": doctor_notes or "",
        "recommendation": recommendation or "",
        "follow_up_days": follow_up_days or 0,
        "is_reviewed": True
    }
    success, result = make_request("PATCH", f"/analyses/{analysis_id}",
                                   token=session_state["token"], json_data=data)
    if success:
        return f"✅ Анализ {analysis_id} обновлён"
    else:
        return f"❌ Ошибка: {result}"


def get_alerts(session_state, status=None, severity=None):
    """Получение алертов для врача или пациента."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    params = {}
    if status:
        params["status"] = status
    if severity:
        params["severity"] = severity

    success, result = make_request("GET", "/alerts", token=session_state["token"], params=params)
    if success:
        if not result:
            return "📭 Нет алертов"
        output = "🚨 АЛЕРТЫ:\n"
        output += "=" * 50 + "\n"
        for a in result:
            output += f"🆔 {a['id']} | Пациент {a['patient_id']}\n"
            output += f"   📊 {a['message']}\n"
            output += f"   ⚠️ Серьёзность: {a['severity']} | Статус: {a['status']}\n"
            output += f"   📅 {a['created_at'][:16]}\n"
            output += "-" * 30 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def resolve_alert(alert_id, session_state):
    """Отметить алерт как решённый (врач)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    if not alert_id:
        return "❌ Введите ID алерта"

    data = {"new_status": "resolved"}
    success, result = make_request("PATCH", f"/alerts/{alert_id}/status",
                                   token=session_state["token"], json_data=data)
    if success:
        return f"✅ Алерт {alert_id} отмечен как решённый"
    else:
        return f"❌ Ошибка: {result}"


# ===================== Административные функции =====================
def admin_list_users(session_state):
    """Список всех пользователей (админ)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/admin/users", token=session_state["token"])
    if success:
        if not result:
            return "📭 Нет пользователей"
        output = "👥 ВСЕ ПОЛЬЗОВАТЕЛИ:\n"
        output += "=" * 60 + "\n"
        for u in result:
            output += f"🆔 {u['id']} | {u['full_name']} ({u['email']})\n"
            output += f"   Роль: {u['role']} | Активен: {u['is_active']}\n"
            output += f"   📅 {u['created_at'][:16]}\n"
            output += "-" * 40 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def admin_assign_doctor(patient_id, doctor_id, session_state):
    """Назначить врача пациенту (админ)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    if not patient_id or not doctor_id:
        return "❌ Введите ID пациента и врача"

    params = {"patient_id": patient_id, "doctor_id": doctor_id}
    success, result = make_request("POST", "/admin/assign-doctor",
                                   token=session_state["token"], params=params)
    if success:
        return f"✅ Врач {doctor_id} назначен пациенту {patient_id}"
    else:
        return f"❌ Ошибка: {result}"


def admin_get_audit_logs(session_state):
    """Просмотр аудит-лога (админ)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    success, result = make_request("GET", "/admin/audit-logs", token=session_state["token"])
    if success:
        if not result:
            return "📭 Нет записей"
        output = "📋 АУДИТ-ЛОГ:\n"
        output += "=" * 60 + "\n"
        for log in result[:30]:
            output += f"🕐 {log['created_at'][:16]} | Пользователь {log['user_id']}\n"
            output += f"   Действие: {log['action_type']} | Цель: {log['target_id']}\n"
            if log['details']:
                output += f"   Детали: {log['details'][:100]}\n"
            output += "-" * 40 + "\n"
        return output
    else:
        return f"❌ Ошибка: {result}"


def admin_delete_user(user_id, session_state):
    """Удалить пользователя (админ)."""
    if not session_state.get("token"):
        return "❌ Сначала войдите"

    if not user_id:
        return "❌ Введите ID пользователя"

    success, result = make_request("DELETE", f"/admin/users/{user_id}",
                                   token=session_state["token"])
    if success:
        return f"✅ Пользователь {user_id} удалён"
    else:
        return f"❌ Ошибка: {result}"


# ===================== Обновление UI =====================
def update_user_info(session_state):
    if session_state.get("profile"):
        name = session_state["profile"].get("full_name", "Unknown")
        role = session_state.get("role", "patient")
        admin_badge = " 👑 (Администратор)" if role == "admin" else ""
        doctor_badge = " 🩺 (Врач)" if role == "doctor" else ""
        return f"""
        <div style="text-align: center; padding: 10px; background-color: #e3f2fd; border-radius: 5px;">
            <p>👤 Пользователь: {name} {admin_badge}{doctor_badge}</p>
            <p>Роль: {role}</p>
        </div>
        """
    else:
        return """
        <div style="text-align: center; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
            <p>👤 Статус: Не авторизован</p>
        </div>
        """


def update_role_based_visibility(session_state):
    role = session_state.get("role", "patient")
    is_admin = (role == "admin")
    is_doctor = (role == "doctor")
    is_patient = (role == "patient")

    # Скрываем/показываем вкладки
    return [
        gr.update(visible=is_patient),          # patient_tab
        gr.update(visible=is_doctor),           # doctor_tab
        gr.update(visible=is_admin)             # admin_tab
    ]


# ===================== Gradio Interface =====================
custom_css = """
.gradio-container { max-width: 1400px !important; margin: 20px auto !important; }
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown("""
    # 🩺 AI Мониторинг диабетической стопы

    Система для сегментации и отслеживания ран.
    """)

    session_state = gr.State({})

    with gr.Tabs():
        # =========== Вкладка 0: Авторизация ===========
        with gr.TabItem("🔐 Вход / Регистрация"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Вход")
                    login_email = gr.Textbox(label="Email", placeholder="email@example.com")
                    login_pass = gr.Textbox(label="Пароль", type="password")
                    login_btn = gr.Button("Войти", variant="primary")
                    logout_btn = gr.Button("🚪 Выйти", variant="stop")
                    delete_account_btn = gr.Button("🗑️ Удалить аккаунт", variant="stop", visible=False)
                with gr.Column():
                    gr.Markdown("### Регистрация (пациент)")
                    reg_email = gr.Textbox(label="Email")
                    reg_name = gr.Textbox(label="Полное имя")
                    reg_pass = gr.Textbox(label="Пароль", type="password")
                    reg_phone = gr.Textbox(label="Телефон", placeholder="+7 999 123-45-67")
                    reg_btn = gr.Button("Зарегистрироваться", variant="secondary")
            auth_output = gr.Textbox(label="Статус", lines=3)

        # =========== Вкладка 1: Пациент ===========
        with gr.TabItem("🧑‍⚕️ Пациент") as patient_tab:
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Загрузить изображение")
                    image_input = gr.Image(type="pil", label="Выберите фото")
                    notes_input = gr.Textbox(label="Заметки")
                    upload_btn = gr.Button("📤 Загрузить", variant="primary")
                    last_image_id = gr.Textbox(label="ID последнего изображения", interactive=False)
                    upload_status = gr.Textbox(label="Статус", lines=2)

                with gr.Column(scale=1):
                    gr.Markdown("### Получить результат")
                    img_id_input = gr.Number(label="ID изображения", precision=0)
                    get_result_btn = gr.Button("📊 Получить результат")
                    result_output = gr.Textbox(label="Результат", lines=12)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Оверлей (маска)")
                    with gr.Row():
                        color_dropdown = gr.Dropdown(
                            choices=["red", "green", "blue", "yellow", "cyan", "magenta", "white"],
                            value="red", label="Цвет контура"
                        )
                        thickness_slider = gr.Slider(minimum=1, maximum=10, value=2, step=1, label="Толщина")
                    show_area_check = gr.Checkbox(value=True, label="Показать площадь")
                    get_overlay_btn = gr.Button("🖼️ Показать оверлей")
                    overlay_image = gr.Image(type="pil", label="Оверлей")
                    overlay_status = gr.Textbox(label="Статус", lines=1)

            with gr.Row():
                with gr.Column():
                    history_btn = gr.Button("📋 История моих загрузок")
                    history_output = gr.Textbox(label="История", lines=10)
                with gr.Column():
                    doctor_btn = gr.Button("👨‍⚕️ Мой врач")
                    doctor_output = gr.Textbox(label="Информация о враче", lines=3)

        # =========== Вкладка 2: Врач ===========
        with gr.TabItem("🩺 Врач") as doctor_tab:
            with gr.Row():
                with gr.Column():
                    patients_btn = gr.Button("👥 Мои пациенты")
                    patients_output = gr.Textbox(label="Пациенты", lines=10)
                with gr.Column():
                    patient_id_input = gr.Number(label="ID пациента для просмотра", precision=0)
                    patient_images_btn = gr.Button("📷 Показать изображения пациента")
                    patient_images_output = gr.Textbox(label="Изображения", lines=10)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Обновить анализ")
                    analysis_id_input = gr.Number(label="ID анализа", precision=0)
                    doctor_notes_input = gr.Textbox(label="Заметки врача", lines=3)
                    recommendation_input = gr.Textbox(label="Рекомендация", lines=2)
                    follow_up_input = gr.Number(label="Дней до следующего осмотра", precision=0)
                    update_analysis_btn = gr.Button("💾 Сохранить изменения")
                    update_analysis_output = gr.Textbox(label="Результат", lines=2)

            with gr.Row():
                with gr.Column():
                    alerts_btn = gr.Button("🚨 Мои алерты")
                    alerts_output = gr.Textbox(label="Алерты", lines=10)
                with gr.Column():
                    alert_id_input = gr.Number(label="ID алерта для решения", precision=0)
                    resolve_alert_btn = gr.Button("✅ Решить алерт")
                    resolve_alert_output = gr.Textbox(label="Результат", lines=2)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Просмотр оверлея")
                    overlay_id_input = gr.Number(label="ID изображения для оверлея", precision=0)
                    color_dropdown = gr.Dropdown(
                        choices=["red","green","blue","yellow","cyan","magenta","white"],
                        value="red", label="Цвет контура"
                    )
                    thickness_slider = gr.Slider(minimum=1, maximum=10, value=2, step=1, label="Толщина")
                    show_area_check = gr.Checkbox(value=True, label="Показать площадь")
                    show_overlay_btn = gr.Button("🖼️ Показать оверлей")
                with gr.Column():
                    overlay_image_display = gr.Image(type="pil", label="Оверлей")
                    overlay_status_display = gr.Textbox(label="Статус", lines=1)

        # =========== Вкладка 3: Админ ===========
        with gr.TabItem("👑 Админ") as admin_tab:
            with gr.Row():
                with gr.Column():
                    users_list_btn = gr.Button("👥 Все пользователи")
                    users_list_output = gr.Textbox(label="Пользователи", lines=12)
                with gr.Column():
                    audit_log_btn = gr.Button("📋 Аудит-лог")
                    audit_log_output = gr.Textbox(label="Логи", lines=12)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Назначить врача пациенту")
                    assign_patient_id = gr.Number(label="ID пациента", precision=0)
                    assign_doctor_id = gr.Number(label="ID врача", precision=0)
                    assign_btn = gr.Button("📌 Назначить")
                    assign_output = gr.Textbox(label="Результат", lines=2)
                with gr.Column():
                    gr.Markdown("### Удалить пользователя")
                    del_user_id = gr.Number(label="ID пользователя", precision=0)
                    del_user_btn = gr.Button("🗑️ Удалить", variant="stop")
                    del_user_output = gr.Textbox(label="Результат", lines=2)
        # =========== Вкладка 4: Профиль ===========
        with gr.TabItem("👤 Профиль"):
            profile_btn = gr.Button("👤 Показать профиль", variant="primary")
            profile_output = gr.Textbox(label="Информация о профиле", lines=10)

    # === Информация о пользователе ===
    user_info = gr.HTML("""
    <div style="text-align: center; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
        <p>👤 Статус: Не авторизован</p>
    </div>
    """)

    # === Обработчики событий ===
    login_btn.click(
        login,
        [login_email, login_pass, session_state],
        [auth_output, session_state, delete_account_btn]
    ).then(
        update_user_info,
        [session_state],
        [user_info]
    ).then(
        update_role_based_visibility,
        [session_state],
        [patient_tab, doctor_tab, admin_tab]
    )

    logout_btn.click(
        logout,
        [session_state],
        [auth_output, session_state, delete_account_btn]
    ).then(
        update_user_info,
        [session_state],
        [user_info]
    ).then(
        update_role_based_visibility,
        [session_state],
        [patient_tab, doctor_tab, admin_tab]
    )

    reg_btn.click(
        register,
        [reg_email, reg_name, reg_pass, reg_phone, session_state],
        [auth_output, session_state]
    )

    # Пациентские
    upload_btn.click(
        upload_wound_image,
        [image_input, notes_input, session_state],
        [upload_status, last_image_id]
    )

    get_result_btn.click(
        get_result,
        [img_id_input, session_state],
        [result_output]
    )

    get_overlay_btn.click(
        get_overlay,
        [img_id_input, color_dropdown, thickness_slider, show_area_check, session_state],
        [overlay_image, overlay_status]
    )

    history_btn.click(
        get_patient_history,
        [session_state],
        [history_output]
    )

    doctor_btn.click(
        get_my_doctor,
        [session_state],
        [doctor_output]
    )

    # Врачебные
    patients_btn.click(
        get_my_patients,
        [session_state],
        [patients_output]
    )

    patient_images_btn.click(
        get_patient_images,
        [patient_id_input, session_state],
        [patient_images_output]
    )

    update_analysis_btn.click(
        update_analysis,
        [analysis_id_input, doctor_notes_input, recommendation_input, follow_up_input, session_state],
        [update_analysis_output]
    )

    alerts_btn.click(
        get_alerts,
        [session_state],
        [alerts_output]
    )

    resolve_alert_btn.click(
        resolve_alert,
        [alert_id_input, session_state],
        [resolve_alert_output]
    )

    # Админские
    users_list_btn.click(
        admin_list_users,
        [session_state],
        [users_list_output]
    )

    audit_log_btn.click(
        admin_get_audit_logs,
        [session_state],
        [audit_log_output]
    )

    assign_btn.click(
        admin_assign_doctor,
        [assign_patient_id, assign_doctor_id, session_state],
        [assign_output]
    )

    del_user_btn.click(
        admin_delete_user,
        [del_user_id, session_state],
        [del_user_output]
    )

    profile_btn.click(
        get_profile,
        [session_state],
        [profile_output]
    )

    show_overlay_btn.click(
        get_overlay, 
        [overlay_id_input, color_dropdown, thickness_slider, show_area_check, session_state],
        [overlay_image_display, overlay_status_display]
    )

    # При загрузке страницы — скрыть вкладки по умолчанию
    demo.load(
        fn=lambda: [gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)],
        outputs=[patient_tab, doctor_tab, admin_tab]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
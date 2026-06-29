import pika
import logging
import json
import time
import sys
import os
import cv2
import numpy as np
import torch
from sqlmodel import select
from datetime import datetime

sys.path.append('/app_app')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


from database.database import get_session
from models.wound_image import WoundImage
from models.wound_analysis import WoundAnalysis
from models.alert import Alert, AlertSeverity, AlertStatus
from models.patient_doctor import PatientDoctorAssignment
from models.audit_log import ActionType
from services.crud.wound_analysis import create_analysis
from services.crud.alert import create_alert
from services.crud.wound_image import update_wound_image
from services.crud.audit_log import log_action
from database.config import get_settings
from albumentations import Compose, Normalize


# Глобальные переменные для модели (загружаются один раз при старте)
settings = get_settings()
model = None
device = None


def tta_predict(model, img_tensor, device, threshold=0.5):
    """TTA с 5 аугментациями + усреднение вероятностей."""
    preds = []
    transforms = [
        lambda x: x,
        lambda x: torch.flip(x, [-1]),
        lambda x: torch.rot90(x, k=1, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=2, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=3, dims=[-2, -1]),
    ]
    inverses = [
        lambda x: x,
        lambda x: torch.flip(x, [-1]),
        lambda x: torch.rot90(x, k=-1, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=-2, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=-3, dims=[-2, -1]),
    ]
    
    with torch.no_grad():
        for t, inv in zip(transforms, inverses):
            aug = t(img_tensor.to(device))
            prob = torch.sigmoid(model(aug)).cpu()
            preds.append(inv(prob))
    
    prob_map = torch.stack(preds).mean(dim=0)
    mask = (prob_map > threshold).float()
    return prob_map, mask


def postprocess_mask(mask: np.ndarray, min_area: int = 100,
                    kernel_size: int = 5):
    """Постобработка: удаление мелких объектов + морфологическое закрытие."""
    # Удаление мелких объектов
    contours, _ = cv2.findContours(
        mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            cv2.drawContours(mask, [cnt], -1, 0, -1)
    
    # Заполнение дырок
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    return mask


def init_model():
    """Загрузка модели сегментации."""
    global model, device
    if model is None:
        logger.info("Загрузка модели сегментации...")
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        from segmentation_models_pytorch import Unet
        model = Unet(
            encoder_name='mit_b1',
            encoder_weights=None,
            in_channels=3,
            classes=1,
            activation=None
        ).to(device)
        # Путь к весам (должен быть доступен внутри контейнера)
        weights_path = os.environ.get('MODEL_WEIGHTS_PATH', '/app/weights/update_model_database_mit.pth')
        checkpoint = torch.load(weights_path, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        logger.info(f"Модель загружена на {device}")
    return model, device


def validate_image_path(image_path):
    """Проверка существования и размера изображения."""
    if not os.path.exists(image_path):
        return False, "File not found"
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False, "Invalid image format"
        h, w = img.shape[:2]
        if h < 50 or w < 50:
            return False, "Image too small (min 50x50)"
        if h > 5000 or w > 5000:
            return False, "Image too large (max 5000x5000)"
        return True, ""
    except Exception as e:
        return False, str(e)


def calculate_area(mask_np):
    """Расчёт площади в пикселях."""
    return int(np.sum(mask_np))
               

def compare_with_previous(current_pct, previous_pct):
    """Вычисление процентного изменения площади."""
    if previous_pct is None:
        return None
    if previous_pct == 0:
        return None  # избегаем деления на ноль
    return ((current_pct - previous_pct) / previous_pct) * 100
    

def check_alert_conditions(change_pct):
    """Определение серьёзности алерта на основе изменения."""
    if change_pct is None:
        return None
    if change_pct > 30:
        return AlertSeverity.CRITICAL
    elif change_pct > 15:
        return AlertSeverity.MEDIUM
    elif change_pct > 5:
        return AlertSeverity.LOW
    return None

    
def process_task(task_json):
    """Обработка одной задачи."""
    image_id = task_json.get('image_id')
    patient_id = task_json.get('patient_id')
    image_path = task_json.get('image_path')
    task_id = task_json.get('task_id', f"task_{image_id}")

    logger.info(f"Получен image_path: {image_path}")
    logger.info(f"Существует ли файл: {os.path.exists(image_path)}")
    logger.info(f"Текущая рабочая директория: {os.getcwd()}")
    logger.info(f"Содержимое /app/uploads: {os.listdir('/app/uploads') if os.path.exists('/app/uploads') else 'папка не существует'}")
    logger.info(f"Начата обработка задачи {task_id} (изображение {image_id})")
    start_time = time.time()
    # Инициализируем модель (если ещё не загружена)
    model, device = init_model()
    # Подключаемся к БД
    session = next(get_session())

    try:
         # 1. Валидация файла
        is_valid, error_msg = validate_image_path(image_path)
        if not is_valid:
            logger.error(f"Ошибка валидации: {error_msg}")
            return

        # 2. Чтение изображения
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            raise ValueError("Не удалось прочитать изображение")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # 3. Предобработка (нормализация)
        transform = Compose([
            Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))
        ])
        transformed = transform(image=img_rgb)
        x = torch.from_numpy(transformed['image']).permute(2, 0, 1).float().unsqueeze(0).to(device)

         # 4. Инференс
        with torch.no_grad():
            _, pred = tta_predict(model, x, device, threshold=0.5)
            mask_np = pred[0, 0].cpu().numpy().astype(np.uint8)
            mask_np = postprocess_mask(mask_np, min_area=100, kernel_size=5)
            
        # --- СОХРАНЕНИЕ МАСКИ ---
        mask_dir = "/app/uploads/masks"
        os.makedirs(mask_dir, exist_ok=True)
        mask_filename = f"mask_{image_id}.png"
        mask_path = os.path.join(mask_dir, mask_filename)
        cv2.imwrite(mask_path, mask_np * 255)  # маска 0/1 -> 0/255
        logger.info(f"Маска сохранена: {mask_path}")

        # 5. Расчёт площади
        area_pixels = calculate_area(mask_np)
        h, w, _ = img_rgb.shape
        area_percent = area_pixels / (h * w)

        # 6. Получение предыдущего изображения пациента
        prev_image = session.exec(
            select(WoundImage)
            .where(WoundImage.patient_id == patient_id)
            .where(WoundImage.id < image_id)
            .order_by(WoundImage.upload_date.desc())
        ).first()
        prev_area_pct = prev_image.wound_area_percentage if prev_image else None
        change_pct = compare_with_previous(area_percent, prev_area_pct)

        # 7. Обновление записи WoundImage
        update_data = {
            "wound_area_pixels": area_pixels,
            "wound_area_percentage": area_percent,
            "area_change_percentage": change_pct,
            "previous_image_id": prev_image.id if prev_image else None,
        }
        image = update_wound_image(image_id, update_data, 
                                   session, skip_permission_check=True)

        # 8. Создание записи WoundAnalysis
        analysis = create_analysis(
            wound_image_id=image_id,
            dice_score=None,
            model_version="unet_mit_b1_v1",
            processing_time_ms=int((time.time() - start_time) * 1000),
            mask_path=mask_path,
            session=session
        )

        # 9. Генерация алерта
        alert = None
        if change_pct is not None:
            severity = check_alert_conditions(change_pct)
            if severity:
                assignment = session.exec(
                    select(PatientDoctorAssignment)
                    .where(PatientDoctorAssignment.patient_id == patient_id)
                    .where(PatientDoctorAssignment.is_active == True)
                ).first()
                doctor_id = assignment.doctor_id if assignment else None
                if doctor_id:
                    alert = create_alert(
                        wound_image_id=image_id,
                        doctor_id=doctor_id,
                        patient_id=patient_id,
                        severity=severity,
                        message=f"Площадь увеличилась на {change_pct:.1f}%",
                        area_change_pct=change_pct,
                        analysis_id=analysis.id,
                        session=session
                    )
                    update_data = {"is_alert": True}
                    update_wound_image(image_id, update_data, session, skip_permission_check=True)

        # 10. Логирование
        log_action(session, ActionType.UPLOAD_IMAGE, patient_id, target_id=str(image_id))

        session.commit()
        elapsed = time.time() - start_time
        logger.info(f"Задача {task_id} выполнена за {elapsed:.2f}с")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        session.rollback()
    finally:
        session.close()


def consumer_loop():

    init_model()
    connection_params = pika.ConnectionParameters(
        host=settings.RMQ_HOST,
        port=settings.RMQ_PORT,
        virtual_host='/',
        credentials=pika.PlainCredentials(
            username=settings.RMQ_USER,
            password=settings.RMQ_PASS
        ),
        heartbeat=60,
        blocked_connection_timeout=2
    )
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    queue_name = 'ml_task_queue'
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        task_json = json.loads(body)
        process_task(task_json)
        # Подписка на очередь и установка обработчика сообщений
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(
    queue=queue_name,
    on_message_callback=callback,
    auto_ack=False  # Автоматическое подтверждение обработки сообщений
    )
    logger.info('Waiting for messages. To exit, press Ctrl+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        consumer_loop()
    except KeyboardInterrupt:
        logger.info("Воркер остановлен")
        sys.exit(0)
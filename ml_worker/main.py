import pika
import logging
import json
import base64
from io import BytesIO
from PIL import Image
import easyocr
import multiprocessing
import time
from sqlmodel import select
import random
import numpy as np

import sys
import os
sys.path.append('/app_app')

from database.database import get_session
from models.model import ML_model
from models.task import Task, TaskDTO, TaskStatus
from services.crud.model import choose_model
from database.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

settings = get_settings()
logger = logging.getLogger(__name__)
# Настройка логирования

reader = None

WORKERS = [
    "worker-1",
    "worker-2",
    "worker-3"
]

def get_model_dir(worker_id):
    model_dir = f"/root/.EasyOCR/models_{worker_id}"
    os.makedirs(model_dir, exist_ok=True)
    return model_dir

def init_reader(worker_id):
    """Инициализация EasyOCR"""
    global reader
    if reader is None:
        logger.info("Загрузка EasyOCR модели...")
        model_dir = get_model_dir(worker_id)
        time.sleep(random.uniform(0, 3))
        reader = easyocr.Reader(
            ['ru', 'en'],
            model_storage_directory=model_dir,
            download_enabled=True,
            gpu=False
        )
        logger.info(f" {worker_id} загрузил EasyOCR")
    return reader


def validate_image(image_data: bytes) -> tuple[bool, str]:
    """
    Валидация изображения перед обработкой
    """
    try:
        # Проверка размера (макс 10MB)
        if len(image_data) > 10 * 1024 * 1024:
            return False, "Image too large (max 10MB)"

        # Проверка, что это действительно изображение
        image = Image.open(BytesIO(image_data))

        # Проверка формата
        if image.format not in ['JPEG', 'PNG', 'BMP', 'TIFF']:
            return False, f"Unsupported image format: {image.format}"

        # Проверка минимального размера
        if image.width < 50 or image.height < 50:
            return False, "Image too small (min 50x50)"

        # Проверка максимального размера
        if image.width > 5000 or image.height > 5000:
            return False, "Image too large (max 5000x5000)"

        return True, ""

    except Exception as e:
        return False, f"Invalid image: {str(e)}"

def process_task(worker_id, task_json):

    task_dto = TaskDTO(**task_json)
    task_id = task_dto.task_id

    logger.info(f"Worker {worker_id} начал обработку задачи {task_id}")
    start_time = time.time()

    try:
        image_data = base64.b64decode(task_dto.input_data)
        is_valid, error_msg = validate_image(image_data)
        if not is_valid:
            logger.error(f"Worker {worker_id}: {error_msg}")
            session = next(get_session())
            task = session.query(Task).filter_by(task_id=task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.output_data = f"Validation error: {error_msg}"
                session.commit()
            session.close()
            return

        image = Image.open(BytesIO(image_data))
        if max(image.size) > 1280:
            ratio = 1280 / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        reader = init_reader(worker_id)
        image_np = np.array(image)
        results = reader.readtext(image_np)
        extracted_text = ' '.join([res[1] for res in results]).strip()

        session = next(get_session())
        model = choose_model(session)
        task = session.query(Task).filter_by(task_id=task_id).first()
        if not task:
            logger.error('Task not found')
            raise ValueError(f"Задача с ID {task_id} не найдена.")

        model.total_predictions += 1
        task.output_data = extracted_text
        task.status = TaskStatus.COMPLETED
        model.successful_predictions += 1
        session.commit()
        session.close()

        elapsed = time.time() - start_time
        logger.info(f" Worker {worker_id} выполнил задачу {task_id} за {elapsed:.2f}с")

        result_dict = {
                "task_id": task_id,
                "prediction": extracted_text.strip(),
                "worker_id": worker_id,
                "status": "success"
        }

        logger.info(f"Worker {worker_id} успешно выполнил задачу {task_id}. "
                    f"Результат: {extracted_text[:50]}...")

        return result_dict

    except Exception as e:
        logger.error(f" Worker {worker_id} ошибка: {str(e)}")
        try:
            session = next(get_session())
            task = session.exec(
                select(Task).where(Task.task_id == task_id)
            ).first()
            if task:
                task.status = TaskStatus.FAILED
                task.output_data = f"Error: {str(e)}"
                session.commit()
            session.close()
        except Exception as db_error:
            logger.error(f"Не удалось обновить статус задачи: {db_error}")


def consumer_loop(worker_id):

    logger.info(f"Worker {worker_id} запущен")
    reader = init_reader(worker_id)

    connection_params = pika.ConnectionParameters(
        host=settings.RMQ_HOST,  # Замените на адрес вашего RabbitMQ сервера
        port=settings.RMQ_PORT,  # Порт по умолчанию для RabbitMQ
        virtual_host='/',  # Виртуальный хост (обычно '/')
        credentials=pika.PlainCredentials(
            username=settings.RMQ_USER,  # Имя пользователя по умолчанию
            password=settings.RMQ_PASS  # Пароль по умолчанию
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
        process_task(worker_id, task_json)
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
    processes = []
    for worker_id in WORKERS:
        p = multiprocessing.Process(target=consumer_loop, args=(worker_id,))
        processes.append(p)
        p.start()

    for proc in processes:
        proc.join()
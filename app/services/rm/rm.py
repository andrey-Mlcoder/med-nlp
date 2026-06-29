import pika
import json
import time
from database.config import get_settings

settings = get_settings()

# Параметры подключения
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

def publish_wound_task(image_id: int, patient_id: int, image_path: str, task_id: str = None) -> None:
    """
    Публикует задачу на сегментацию в очередь.
    
    Args:
        image_id: ID записи WoundImage
        patient_id: ID пациента
        image_path: путь к файлу изображения
        task_id: опциональный идентификатор задачи (генерируется автоматически)
    """

    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    queue_name = 'ml_task_queue'
    channel.queue_declare(queue=queue_name, durable=True)

    if task_id is None:
        task_id = f"task_{image_id}_{int(time.time())}"

    task_data = {
        "image_id": image_id,
        "patient_id": patient_id,
        "image_path": image_path,
        "task_id": task_id
    }

    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(task_data),
    )
    # Закрытие соединения
    connection.close()
import pika
from sqlmodel import Session
from models.task import TaskDTO, Task
from database.config import get_settings

settings = get_settings()

# Параметры подключения
connection_params = pika.ConnectionParameters(
    host=settings.RMQ_HOST,  # Замените на адрес вашего RabbitMQ сервера
    port=settings.RMQ_PORT,          # Порт по умолчанию для RabbitMQ
    virtual_host='/',   # Виртуальный хост (обычно '/')
    credentials=pika.PlainCredentials(
        username=settings.RMQ_USER,  # Имя пользователя по умолчанию
        password=settings.RMQ_PASS   # Пароль по умолчанию
    ),
    heartbeat=60,
    blocked_connection_timeout=2
)

def publish_ml_task(task: Task, session: Session):

    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    queue_name = 'ml_task_queue'
    channel.queue_declare(queue=queue_name, durable=True)

    task = TaskDTO(task_id=task.task_id,
                   input_data=task.input_data,
                   status=task.status.value
                   )

    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=task.json(),
    )
    # Закрытие соединения
    connection.close()
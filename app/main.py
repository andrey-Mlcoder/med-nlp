from database.config import get_settings
from database.database import get_session, init_db, get_database_engine
from services.crud.user import get_all_users
from services.crud.model import get_all_models
from sqlalchemy.orm import Session

if __name__ == "__main__":
    settings = get_settings()
    print(settings.APP_NAME)
    print(settings.API_VERSION)
    print(f'Debug: {settings.DEBUG}')
    
    print(settings.DB_HOST)
    print(settings.DB_NAME)
    print(settings.DB_USER)
    
    init_db(drop_all=True)
    print('Init db has been success')

    engine = get_database_engine()
    
    with Session(engine) as session:
        users = get_all_users(session)
        models = get_all_models(session)
        
        print(f"nНайдено пользователей: {len(users)}")
        for user in users:
            print(f" Name: {user.username}, email: {user.email}, balance: {user.balance.amount if user.balance else 0.0}")
            
        for user in users[:3]:  # Показываем первые 3 пользователя
            print(f"Пользователь: {user.username}")
            print(f"ID: {user.user_id}")
            print(f"Баланс: {user.balance.amount if user.balance else 0.0}")
            
            if not user.tasks or len(user.tasks) == 0:
                print("Задачи: нет задач")
            else:
                print(f"Задачи: {len(user.tasks)}")
                for task in user.tasks[:2]:  # Показываем первые 2 задачи
                    print(f"  - {task.description}: {task.status.value}")

        print(" Инициализация завершена успешно!")
from models.user import User
from models.balance import Balance
from models.transaction import Transaction
from models.admin import Admin
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime


def get_all_transactions(session: Session) -> List[Transaction]:
    
    try:
        statement = select(Transaction)
        transactions = session.exec(statement).all()
        return transactions
    except Exception as e:
        raise

def make_decision(request: dict, session: Session) -> dict:

    amount = request.get("amount", 0)
    if amount > 0:
        return {"status": "approved", "message": "Запрос одобрен"}
    else:
        return {"status": "denied", "message": "Запрос отклонен"}
    
def add_to_history(admin_id: int, user_id: int, amount: float, session: Session):
    admin = session.get(Admin, admin_id)
    if admin:
        admin.add_to_history(user_id, amount, f"Добавление баланса через админа {admin_id}")
        session.commit()
        
def add_balance_to_user(admin_id: int, user_id: int, amount: float, session: Session) -> Optional[User]:
    
    user = session.get(User, user_id)
    if user:
            user.balance.amount += amount
            session.commit()
            session.refresh(user)
            add_to_history(admin_id, user_id, amount, session)
            return user
    return None


def create_admin(username: str, email: str, password: str, session: Session) -> Admin:
    try:
        from auth.hash_password import HashPassword
        hash_password = HashPassword()

        #  Создаем пользователя
        user = User(
            username=username,
            email=email,
            password=hash_password.create_hash(password)
        )

        # Создаем баланс для пользователя
        balance = Balance(
            amount=0.0,
            user_id=None
        )
        user.balance = balance

        session.add(user)
        session.flush()

        if user.balance:
            user.balance.user_id = user.user_id

        # Создаем запись в таблице admin
        admin = Admin(
            username=username,
            created_at=datetime.now(),
            history='{}'
        )
        session.add(admin)

        session.commit()
        session.refresh(admin)

        print(f"Администратор создан: {email}")
        return admin

    except Exception as e:
        session.rollback()
        print(f"Ошибка создания администратора: {e}")
        raise


def create_test_admin(session: Session) -> Admin:
    """
    Создание тестового администратора
    """
    try:
        from auth.hash_password import HashPassword
        from datetime import datetime

        hash_password = HashPassword()

        # Данные тестового админа
        username = "admin"
        email = "admin@example.com"
        password = "admin123"

        # 1️⃣ Проверяем, не существует ли уже
        from models.user import User
        existing_user = session.exec(select(User).where(User.email == email)).first()
        if existing_user:
            print(f"⚠Пользователь {email} уже существует")
            existing_admin = session.exec(select(Admin).where(Admin.username == username)).first()
            if existing_admin:
                return existing_admin

        user = User(
            username=username,
            email=email,
            password=hash_password.create_hash(password)
        )

        balance = Balance(amount=100.0)
        user.balance = balance

        session.add(user)
        session.flush()

        if user.balance:
            user.balance.user_id = user.user_id

        admin = Admin(
            username=username,
            created_at=datetime.now(),
            history='{}'
        )
        session.add(admin)

        session.commit()

        return admin

    except Exception as e:
        session.rollback()
        print(f"Ошибка: {e}")
        raise
from sqlmodel import SQLModel, Session, create_engine, select 
from .config import get_settings
from auth.hash_password import HashPassword
from models.user import User, UserRole
from models.patient_doctor import PatientDoctorAssignment

def get_database_engine():
    """
    Create and configure the SQLAlchemy engine.
    
    Returns:
        Engine: Configured SQLAlchemy engine
    """
    settings = get_settings()
    
    engine = create_engine(
        url=settings.DATABASE_URL_psycopg,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    return engine

engine = get_database_engine()

def get_session():
    with Session(engine) as session:
        yield session
        
def init_db(drop_all: bool = False) -> None:
    """
    Инициализация базы данных: создание таблиц и тестовых пользователей.
    """
    try:
        engine = get_database_engine()
        if drop_all:
            SQLModel.metadata.drop_all(engine)
        
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Проверяем, есть ли уже пользователи
            existing_users = session.exec(select(User)).all()
            if not existing_users:
                hash_pwd = HashPassword()

                # 1. Создаём администратора
                admin = User(
                    email="admin@example.com",
                    hashed_password=hash_pwd.create_hash("admin123"),
                    full_name="Test Admin",
                    role=UserRole.ADMIN,
                    is_active=True
                )
                session.add(admin)

                # 2. Создаём врача
                doctor = User(
                    email="doctor@example.com",
                    hashed_password=hash_pwd.create_hash("doctor123"),
                    full_name="Test Doctor",
                    role=UserRole.DOCTOR,
                    is_active=True,
                    specialization="Wound Care Specialist"
                )
                session.add(doctor)

                # 3. Создаём пациента
                patient = User(
                    email="patient@example.com",
                    hashed_password=hash_pwd.create_hash("patient123"),
                    full_name="Test Patient",
                    role=UserRole.PATIENT,
                    is_active=True,
                    phone="+7 999 123-45-67"
                )
                session.add(patient)

                session.commit()
                session.refresh(admin)
                session.refresh(doctor)
                session.refresh(patient)

                # 4. Назначаем врача пациенту
                assignment = PatientDoctorAssignment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    is_active=True
                )
                session.add(assignment)
                session.commit()

                print("✅ Тестовые пользователи созданы:")
                print(f"   Админ: admin@example.com / admin123")
                print(f"   Врач:  doctor@example.com / doctor123")
                print(f"   Пациент: patient@example.com / patient123")
            else:
                print("ℹ️ Пользователи уже существуют, пропускаем создание.")

    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise
        
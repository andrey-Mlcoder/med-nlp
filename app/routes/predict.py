from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,  Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from database.database import get_session
from services.crud.wound_image import create_wound_image, get_wound_image, get_patient_images
from services.crud.wound_analysis import update_analysis
from services.crud.user import get_user_by_email
from auth.authenticate import authenticate
from services.rm.rm import publish_wound_task
from models.user import User
from models.wound_analysis import WoundAnalysis
from typing import Dict, List
import logging
import os
import shutil
import cv2
import numpy as np
from io import BytesIO

logger = logging.getLogger(__name__)
predict_router = APIRouter()


def get_current_user(token: str = Depends(authenticate), session: Session = Depends(get_session)) -> User:
    user = get_user_by_email(token, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@predict_router.post('/upload')
def upload_image(file: UploadFile = File(...),
                       current_user: User = Depends(get_current_user),
                       session: Session = Depends(get_session)
                      ):
    # Сохраняем файл
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{current_user.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Создаём запись
    image = create_wound_image(
        patient_id=current_user.id,
        image_path=file_path,
        original_filename=file.filename,
        session=session,
        current_user=current_user
    )

    # Отправляем задачу воркеру
    publish_wound_task(image.id, current_user.id, file_path)

    return {"image_id": image.id, "message": "Processing started"}


@predict_router.get("/result/{image_id}")
def get_result(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
)-> Dict:
    image = get_wound_image(image_id, session, current_user)
    if not image:
        raise HTTPException(404, "Image not found")
    analysis = session.exec(
        select(WoundAnalysis)
        .where(WoundAnalysis.wound_image_id == image_id)
        .order_by(WoundAnalysis.created_at.desc())
    ).first()
    if analysis:
        return {
            "image_id": image.id,
            "area_percent": image.wound_area_percentage,
            "area_change": image.area_change_percentage,
            "alert": image.is_alert,
            "dice": analysis.dice_score,
            "model": analysis.model_version,
            "processing_time_ms": analysis.processing_time_ms
            }
    # Если анализ ещё не готов
    return {"status": "processing", "image_id": image.id}


@predict_router.get('/overlay/{image_id}')
def get_overlay(
    image_id: int,
    color: str = Query("red", regex="^(red|green|blue|yellow|cyan|magenta|white)$", description="Цвет контура"),
    thickness: int = Query(2, ge=1, le=10, description="Толщина контура в пикселях"),
    show_area: bool = Query(True, description="Показывать площадь раны на изображении"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Возвращает изображение с контуром маски сегментации.
    Доступ: пациент – только свои, врач – своих пациентов, администратор – все.
    """
    # Проверяем доступ к изображению
    image = get_wound_image(image_id, session, current_user)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found or access denied")
    
    # Проверяем наличие анализа и маски
    analysis = session.exec(
    select(WoundAnalysis)
    .where(WoundAnalysis.wound_image_id == image_id)
    .order_by(WoundAnalysis.created_at.desc())
).first()
    if not analysis or not analysis.mask_path:
        raise HTTPException(status_code=404, detail="Mask not found for this image")
    
    # Загружаем исходное изображение и маску
    img = cv2.imread(image.image_path)
    mask = cv2.imread(analysis.mask_path, cv2.IMREAD_GRAYSCALE)
    
    if img is None:
        logger.error(f"Не удалось загрузить изображение по пути: {image.image_path}")
        raise HTTPException(status_code=404, detail="Image file not found")
    if mask is None:
        logger.error(f"Не удалось загрузить маску по пути: {analysis.mask_path}")
        raise HTTPException(status_code=404, detail="Mask file not found")
    
    # Приводим маску к размеру изображения
    if mask.shape != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
    
    # Бинаризуем маску
    mask_bin = (mask > 127).astype(np.uint8)
    
    # Находим контуры
    contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Определяем цвет в формате BGR
    color_map = {
        "red": (0, 0, 255),
        "green": (0, 255, 0),
        "blue": (255, 0, 0),
        "yellow": (0, 255, 255),
        "cyan": (255, 255, 0),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255)
    }
    color_bgr = color_map.get(color, (0, 0, 255))
    
    # Рисуем контуры на изображении
    cv2.drawContours(img, contours, -1, color_bgr, thickness)
    
    # Добавляем информацию о площади, если запрошено
    if show_area and image.wound_area_percentage is not None:
        area_text = f"Area: {image.wound_area_percentage*100:.2f}%"
        if image.wound_area_cm2:
            area_text += f" ({image.wound_area_cm2:.2f} cm²)"
        # Добавляем фон для текста для лучшей читаемости
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness_text = 2
        (text_w, text_h), baseline = cv2.getTextSize(area_text, font, font_scale, thickness_text)
        # Прямоугольник под текст (полупрозрачный)
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (10 + text_w + 10, 10 + text_h + 10), (0, 0, 0), -1)
        img = cv2.addWeighted(img, 0.6, overlay, 0.4, 0)
        # Пишем текст
        cv2.putText(img, area_text, (20, 10 + text_h + 5), font, font_scale, (255, 255, 255), thickness_text)
    
    # Кодируем результат в PNG
    success, buffer = cv2.imencode('.png', img)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode image")
    
    return StreamingResponse(
        BytesIO(buffer.tobytes()),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=overlay_{image_id}.png"}
    )


@predict_router.get('/images/patient/{patient_id}')
def get_patient_images_endpoint(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> List:
    """Получить все изображения конкретного пациента (для врача)."""
    images = get_patient_images(patient_id, session, current_user)
    return [
        {
            "id": img.id,
            "upload_date": img.upload_date.isoformat(),
            "wound_area_percentage": img.wound_area_percentage,
            "is_alert": img.is_alert
        }
        for img in images
    ]


@predict_router.patch('/analyses/{analysis_id}')
def update_analysis_endpoint(
    analysis_id: int,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    analysis = update_analysis(analysis_id, update_data, session, current_user)
    return {"message": "Analysis updated"}
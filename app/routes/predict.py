from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Query
from sqlmodel import Session, select
from database.database import get_session
from models.task import Task, TaskStatus
from services.crud import user as UserService
from services.crud import task as TaskService
from services.rm.rm import publish_ml_task
from typing import Dict
from auth.authenticate import authenticate
import base64
import logging
import time
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

predict_router = APIRouter()

@predict_router.post('/upload_image',
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Upload image",
    description="Upload image and see magic of ML")
async def upload_image(file: UploadFile = File(...),
    token: str = Depends(authenticate),
    cost: float = Query(...),
    description: str = Query(None),
    session=Depends(get_session)
)-> Dict[str, str]:
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        encoded_image = base64.b64encode(contents).decode("utf-8")

        task = TaskService.create_database_task(user.user_id, encoded_image, cost, description, session)

        if not task:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create task (insufficient funds or other error)")

        publish_ml_task(task, session)

        return {"task_id": task.task_id}

    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Server error")

@predict_router.get("/get-result/{task_id}")
async def get_result(task_id: str, token: str = Depends(authenticate),
                     session=Depends(get_session)):
    """
    Long polling для получения результата задачи.
    """
    max_wait_time = 60  # Максимальное время ожидания (60 секунд)
    start_time = time.time()

    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        task = session.exec(select(Task).where(
            Task.task_id == task_id,
            Task.user_id == user.user_id)).first()

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
        )

        while True:
            session.refresh(task)

            if task.status == TaskStatus.COMPLETED:
                result = {
                "task_id": task.task_id,
                "prediction": task.output_data,
                "status": task.status.value
            }
                return result
            elif task.status == TaskStatus.FAILED:
                result = {
                    "task_id": task.task_id,
                    "prediction": "failed",
                    "status": task.status.value
                }
                return result
            elif time.time() - start_time > max_wait_time:
                return {"detail": "Timeout waiting for task completion"}
            else:
                await asyncio.sleep(1)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting result: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving task result"
        )
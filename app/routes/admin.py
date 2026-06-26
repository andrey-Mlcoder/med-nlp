from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from database.database import get_session
from models.user import User
from models.admin import Admin
from models.transaction import Transaction
from auth.authenticate import authenticate
from services.crud import user as UserService
from services.crud import admin as AdminService
from services.crud import balance as BalanceService
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

admin_router = APIRouter()


def check_admin(token: str = Depends(authenticate), session=Depends(get_session)):
    """Проверка, является ли пользователь администратором"""
    user = UserService.get_user_by_email(token, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Проверяем, есть ли пользователь в таблице Admin
    admin = session.exec(select(Admin).where(Admin.username == user.username)).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return admin


@admin_router.get('/check')
async def check_is_admin(
        token: str = Depends(authenticate),
        session=Depends(get_session)
) -> Dict[str, Any]:
    """Проверка, является ли пользователь администратором"""
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            return {"is_admin": False}

        admin = session.exec(select(Admin).where(Admin.username == user.username)).first()
        return {
            "is_admin": admin is not None,
            "username": user.username
        }
    except Exception as e:
        logger.error(f"Error checking admin: {str(e)}")
        return {"is_admin": False}


@admin_router.get('/users')
async def get_all_users(
        admin: Admin = Depends(check_admin),
        session=Depends(get_session)
) -> List[Dict[str, Any]]:
    """
    Просмотр всех пользователей
    """
    try:
        users = UserService.get_all_users(session)
        result = []
        for user in users:
            user_info = user.get_info()
            user_info['created_at'] = str(user.created_at)
            # Добавляем статистику
            user_info['tasks_count'] = len(user.tasks) if user.tasks else 0
            result.append(user_info)
        return result
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving users"
        )


@admin_router.post('/users/{user_id}/balance')
async def admin_add_balance(
        user_id: int,
        amount: float = Query(..., description="Amount to add", gt=0),
        admin: Admin = Depends(check_admin),
        session=Depends(get_session)
) -> Dict[str, Any]:
    """
    Пополнение баланса пользователя администратором
    """
    try:
        updated_user = AdminService.add_balance_to_user(admin.admin_id, user_id, amount, session)

        if updated_user and updated_user.balance:
            return {
                "success": True,
                "message": "Balance added successfully",
                "user_id": user_id,
                "username": updated_user.username,
                "amount": amount,
                "new_balance": updated_user.balance.amount
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add balance"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding balance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@admin_router.get('/transactions')
async def get_all_transactions(
        admin: Admin = Depends(check_admin),
        limit: int = Query(100, description="Number of transactions"),
        session=Depends(get_session)
) -> List[Dict[str, Any]]:
    """
    Просмотр всех транзакций в системе
    """
    try:
        transactions = AdminService.get_all_transactions(session)

        result = []
        for t in sorted(transactions, key=lambda x: x.created_at, reverse=True)[:limit]:
            user = None
            if t.balance and t.balance.user:
                user = t.balance.user

            result.append({
                "transaction_id": t.transaction_id,
                "amount": t.amount,
                "created_at": str(t.created_at),
                "user_id": user.user_id if user else None,
                "username": user.username if user else "Unknown"
            })

        return result
    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving transactions"
        )


@admin_router.post('/moderate-deposit')
async def moderate_deposit(
        user_id: int,
        amount: float = Query(..., gt=0),
        decision: str = Query(..., regex="^(approve|reject)$"),
        admin: Admin = Depends(check_admin),
        session=Depends(get_session)
) -> Dict[str, Any]:
    """
    Модерация пользовательского пополнения
    """
    try:
        decision_result = AdminService.make_decision({"amount": amount}, session)

        if decision_result["status"] == "approved" and decision == "approve":
            updated_user = AdminService.add_balance_to_user(admin.admin_id, user_id, amount, session)
            AdminService.add_to_history(admin.admin_id, user_id, amount,
                                        f"Одобрено пополнение на {amount}")
            return {
                "status": "approved",
                "message": f"Пополнение на {amount} кредитов одобрено",
                "user_id": user_id,
                "amount": amount,
                "new_balance": updated_user.balance.amount if updated_user else None
            }
        elif decision == "reject":
            AdminService.add_to_history(admin.admin_id, user_id, amount,
                                        f"Отклонено пополнение на {amount}")
            return {
                "status": "rejected",
                "message": f"Пополнение на {amount} кредитов отклонено",
                "user_id": user_id,
                "amount": amount
            }
        else:
            return {
                "status": decision_result["status"],
                "message": decision_result["message"]
            }
    except Exception as e:
        logger.error(f"Error moderating deposit: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@admin_router.get('/history')
async def get_admin_history(
        admin: Admin = Depends(check_admin)
) -> Dict[str, Any]:
    """
    Просмотр истории действий администратора
    """
    try:
        history = admin.get_history()
        formatted_history = []
        for user_id, actions in history.items():
            for action in actions:
                formatted_history.append({
                    "user_id": int(user_id),
                    "amount": action.get("amount"),
                    "description": action.get("description"),
                    "timestamp": action.get("timestamp")
                })

        # Сортируем по времени (сначала новые)
        formatted_history.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "admin_id": admin.admin_id,
            "username": admin.username,
            "history": formatted_history[:50]
        }
    except Exception as e:
        logger.error(f"Error getting admin history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving admin history"
        )


@admin_router.delete('/users/{user_id}')
async def admin_delete_user(
        user_id: int,
        admin: Admin = Depends(check_admin),
        session=Depends(get_session)
) -> Dict[str, Any]:
    """
    Удаление пользователя администратором
    """
    try:
        from services.crud.user import delete_user
        result = delete_user(user_id, session)

        if result:
            return {
                "success": True,
                "message": f"User {user_id} has been deleted by admin"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )
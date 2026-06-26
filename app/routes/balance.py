from fastapi import APIRouter, HTTPException, status, Depends, Query
from database.database import get_session
from services.crud import user as UserService
from services.crud import balance as BalanceService
from auth.authenticate import authenticate
from typing import Dict
import logging

# Configure logging
logger = logging.getLogger(__name__)

balance_router = APIRouter()

@balance_router.get('/current_balance',
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Current user balance"
)
async def current_balance(token: str = Depends(authenticate),
                          session=Depends(get_session)
                          )-> Dict[str, str]:
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        balance = BalanceService.get_balance_by_user_id(user.user_id, session)
        
        return {"user_id": str(user.user_id),
                "email": user.email,
                "amount": str(balance.amount),
                "message": "Balance retrieved successfully"}
        
    except Exception as e:
        logger.error(f"Balance error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Balance not found")

@balance_router.post('/add_balance',
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Add credits to user balance")
async def add_balance(token: str = Depends(authenticate),
    amount: float = Query(..., description="Amount to add", gt=0),
    session=Depends(get_session)
) -> Dict[str, str]:
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        updated_balance = UserService.add_balance(user.user_id, amount, session)
        if updated_balance:
            return {"message": "Balance updated successfully",
                    "user_id": str(user.user_id),
                    "new_balance": str(updated_balance.amount)}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update balance or user not found")
        
    except Exception as e:
        logger.error(f"Add balance error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add balance error")

@balance_router.post('/spend_balance',
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Spend credits to user task")
async def spend_balance(token: str = Depends(authenticate),
    amount: float = Query(..., description="Amount to add"),
    session=Depends(get_session)) -> Dict[str, str]:
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        updated_balance = BalanceService.spend(user.user_id, amount, session)
        if updated_balance:
            return {"message": "Balance spent successfully",
                    "user_id": str(user.user_id),
                    "new_balance": str(updated_balance.amount)}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient funds")
        
    except Exception as e:
        logger.error(f"Balance error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spend balance error")
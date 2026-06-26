from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from auth.authenticate import authenticate
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from database.database import get_session
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from models.user import User
from services.crud import user as UserService
from typing import Dict, List
import logging

# Configure logging
logger = logging.getLogger(__name__)

users_router = APIRouter()
hash_password = HashPassword()

@users_router.post('/signup',
                  response_model=Dict[str, str],
                  status_code=status.HTTP_201_CREATED,
                  summary="User Registration",
                  description="Register a new user with email and password")
async def signup(user: User, session=Depends(get_session)) -> Dict[str, str]:
    """
    Create new user account.

    Args:
        user: User registration data
        session: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If user already exists
    """
    try:
        user_exist = UserService.get_user_by_email(user.email, session)
        if user_exist:
            logger.warning(f"Signup attempt with existing email: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists")

        hashed_password = hash_password.create_hash(user.password)
        user.password = hashed_password
        UserService.create_user(user, session)
        logger.info(f"New user registered: {user.email}")

        return {"message": "User successfully registered"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )

@users_router.post('/signin',
                  response_model=Dict[str, str],
                  status_code=status.HTTP_200_OK,
                  summary="User authentication",
                  description="Authenticate a new user with email and password")
async def signin(form_data: OAuth2PasswordRequestForm = Depends(),
                 session=Depends(get_session)) -> Dict[str, str]:
    """
    Authenticate existing user.

    Args:
        user: User credentials
        session: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If authentication fails
    """
    user_exist = UserService.get_user_by_email(form_data.username, session)
    if user_exist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist")

    if hash_password.verify_hash(form_data.password, user_exist.password):
        access_token = create_access_token(user_exist.email)
        return {"access_token": access_token, "token_type": "Bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid details passed."
    )

@users_router.get('/history',
    status_code=status.HTTP_200_OK,
    summary="User History",
    description="user history sorted from recent to oldest")
async def history(token: str=Depends(authenticate),
                  session=Depends(get_session)) -> List[Dict]:
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        history = UserService.get_user_history(user.user_id, session)
        return history

    except Exception as e:
        logger.error(f"User history error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User history not found")

@users_router.get('/profile',
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="User profile")
async def show_user(token: str=Depends(authenticate), session=Depends(get_session)) -> Dict[str, str]:
  
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user_profile = user.get_info()
        return {"user_id": str(user_profile["user_id"]),
                "username": user_profile["username"],
                "email": user_profile["email"],
                "balance": str(user_profile["balance"])}

    except Exception as e:
        logger.error(f"User error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found")

@users_router.delete('/profile',
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Delete user",
    description="delete user by user id")
async def delete_user(user_id: int, token: str=Depends(authenticate),
                      session=Depends(get_session)) -> Dict[str, str]:
  
    try:
        user = UserService.get_user_by_email(token, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user not found"
            )

        if user.user_id != user_id:
            raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account")

        delete_user = UserService.delete_user(user_id, session)
        if delete_user:
            return {"message": f"User {user_id} has been deleted"}
        
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error")
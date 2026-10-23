from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.auth.login_user import LoginUser
from app.application.auth.register_user import RegisterUser
from app.domain.entities.user import User
from app.presentation.http.dependencies import CurrentUser, get_login_user, get_register_user
from app.presentation.http.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, is_active=user.is_active, created_at=user.created_at
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register(
    body: RegisterRequest, use_case: Annotated[RegisterUser, Depends(get_register_user)]
) -> UserResponse:
    return to_response(use_case.execute(body.email, body.password))


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, use_case: Annotated[LoginUser, Depends(get_login_user)]
) -> TokenResponse:
    token = use_case.execute(body.email, body.password)
    return TokenResponse(access_token=token.token, expires_at=token.expires_at)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return to_response(user)

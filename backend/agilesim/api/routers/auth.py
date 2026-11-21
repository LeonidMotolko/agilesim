"""Facilitator accounts: ``POST /v1/auth/register`` and ``POST /v1/auth/login``."""

from fastapi import APIRouter, status

from agilesim.api.deps import AuthServiceDep
from agilesim.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, service: AuthServiceDep) -> TokenResponse:
    """Create a facilitator account and return an access token."""
    return service.register(request)


@router.post("/login")
def login(request: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    """Exchange e-mail and password for an access token."""
    return service.login(request)

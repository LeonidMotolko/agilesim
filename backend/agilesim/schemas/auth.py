"""Request and response bodies of the account endpoints."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from agilesim.core.constants import MAX_NAME_LENGTH, MIN_PASSWORD_LENGTH

# A deliberately simple shape check; the database also requires a lower-case address with an "@".
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
DisplayName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_LENGTH)
]


class RegisterRequest(BaseModel):
    email: Email
    display_name: DisplayName
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    role: str

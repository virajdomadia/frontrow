"""Auth contract (06 §C): `Me`, sign-up / sign-in bodies, demo, bearer tokens."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel

Role = Literal["customer", "organiser"]


class Me(ApiModel):
    id: UUID
    name: str
    email: str
    role: Role


class SignUp(ApiModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    role: Role = "customer"


class SignIn(ApiModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=200)


class Demo(ApiModel):
    as_: Role = Field(alias="as", description="Which seeded demo account to sign in as.")


class Token(ApiModel):
    token: str = Field(description="Send as `Authorization: Bearer <token>`.")
    expires_at: datetime
    me: Me

"""Auth contract (06 §C): `Me`, the email-code bodies, demo sign-in, bearer tokens."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel

Door = Literal["customer", "business", "staff"]
BusinessStatus = Literal["pending", "verified", "rejected", "suspended"]


class BusinessRef(ApiModel):
    id: UUID
    name: str
    slug: str
    status: BusinessStatus
    role: str


class Me(ApiModel):
    id: UUID
    name: str
    email: str
    is_staff: bool
    is_demo: bool = Field(
        description="A one-click demo account (never emailed; staff demo is view-only)."
    )
    businesses: list[BusinessRef] = Field(description="Business access on top of the account.")


class CodeRequest(ApiModel):
    email: str = Field(max_length=254)
    door: Door = "customer"


class BusinessDetails(ApiModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=6, max_length=20, pattern=r"^[0-9+()\- ]+$")
    logo_url: str | None = Field(default=None, pattern=r"^/img/logos/[a-z0-9-]+\.svg$")


class Verify(ApiModel):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r"^\d{6}$")
    door: Door = "customer"
    name: str | None = Field(default=None, max_length=80)
    business: BusinessDetails | None = None


class Demo(ApiModel):
    as_: Literal["customer", "owner", "staff"] = Field(
        alias="as", description="Which seeded demo account to sign in as."
    )


class TokenRequest(ApiModel):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r"^\d{6}$")


class Token(ApiModel):
    token: str = Field(description="Send as `Authorization: Bearer <token>`.")
    expires_at: datetime
    me: Me

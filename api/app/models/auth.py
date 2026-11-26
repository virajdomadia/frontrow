"""users + sessions (06 §A). Sign-in is by email code only, so there is no password column.
One email = one person: every user can book; business access (`business_members`) and the staff
flag sit on top. `sessions.kind` ships in v1 so the v4 app's bearer tokens are just rows with
kind = mobile."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import SessionKind


class User(UuidMixin, CreatedMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # stored lowercased
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(CreatedMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # HMAC of the cookie / bearer value
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The anonymous fr_sid this session adopted, so holds made before sign-in stay "mine".
    sid: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[SessionKind] = mapped_column(
        pg_enum(SessionKind, "session_kind"), nullable=False, server_default=SessionKind.WEB.value
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class OAuthCode(Base):
    """Short-lived authorization codes issued during the account-linking flow."""
    __tablename__ = "oauth_codes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(256), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OAuthToken(Base):
    """Issued access + refresh tokens for Alexa / Google account linking."""
    __tablename__ = "oauth_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    access_token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    refresh_token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
